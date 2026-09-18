use base64::{engine::general_purpose::STANDARD, Engine as _};
use rand::RngCore;
use std::{
    fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
    thread,
    time::Duration,
};
use tauri::{Manager, RunEvent};

const KEYCHAIN_SERVICE: &str = "com.lqq.supportflow.model-secret.v1";
const KEYCHAIN_ACCOUNT: &str = "MODEL_SECRET_MASTER_KEY";
const HEALTH_WAIT_POLLS: u64 = 240;

struct BackendProcess(Mutex<Option<Child>>);

fn backend_is_healthy() -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], 8080));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(500)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    if stream
        .write_all(b"GET /actuator/health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }
    let mut response = String::new();
    stream.read_to_string(&mut response).is_ok()
        && response.starts_with("HTTP/1.1 200")
        && response.contains("\"status\":\"UP\"")
}

fn model_secret() -> Result<String, String> {
    let entry = keyring::Entry::new(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        .map_err(|_| "cannot access the system credential store".to_owned())?;
    if let Ok(existing) = entry.get_password() {
        return Ok(existing);
    }

    let mut bytes = [0_u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    let generated = STANDARD.encode(bytes);
    entry
        .set_password(&generated)
        .map_err(|_| "cannot save the local model key in the system credential store".to_owned())?;
    Ok(generated)
}

fn packaged_backend_path(app: &tauri::AppHandle) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let resources = app.path().resource_dir()?;
    #[cfg(target_os = "macos")]
    return Ok(resources.join("SupportFlowBackend.app/Contents/MacOS/SupportFlowBackend"));
    #[cfg(target_os = "windows")]
    return Ok(resources.join("SupportFlowBackend/SupportFlowBackend.exe"));
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    return Ok(resources.join("SupportFlowBackend/SupportFlowBackend"));
}

fn start_packaged_backend(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    if cfg!(debug_assertions) {
        return Ok(());
    }
    if backend_is_healthy() {
        return Ok(());
    }

    let data_dir = app.path().app_data_dir()?;
    fs::create_dir_all(data_dir.join("data"))?;
    fs::create_dir_all(data_dir.join("logs"))?;
    let mut child = Command::new(packaged_backend_path(app)?)
        .env(
            "MODEL_SECRET_MASTER_KEY",
            model_secret().map_err(std::io::Error::other)?,
        )
        .env("SUPPORTFLOW_DESKTOP_DATA_DIR", data_dir.join("data"))
        .env("SUPPORTFLOW_MODEL_MOCK_ENABLED", "false")
        .arg("--spring.profiles.active=desktop")
        .stdout(fs::File::create(data_dir.join("logs/backend.out.log"))?)
        .stderr(fs::File::create(data_dir.join("logs/backend.err.log"))?)
        .spawn()?;
    for _ in 0..HEALTH_WAIT_POLLS {
        if backend_is_healthy() {
            *app.state::<BackendProcess>()
                .0
                .lock()
                .expect("backend process lock") = Some(child);
            return Ok(());
        }
        if child.try_wait()?.is_some() {
            return Err("packaged SupportFlow backend exited before becoming healthy".into());
        }
        thread::sleep(Duration::from_millis(250));
    }
    let _ = child.kill();
    return Err("packaged SupportFlow backend did not become healthy within 60 seconds".into());
}

/// Re-launch the packaged backend after a failed start. Invoked by the login
/// page's reconnect button so a slow first boot no longer requires restarting
/// the whole client.
#[tauri::command]
fn restart_backend(app: tauri::AppHandle) -> Result<(), String> {
    if backend_is_healthy() {
        return Ok(());
    }
    if cfg!(debug_assertions) {
        return Err("dev mode: start the backend with mvn spring-boot:run".into());
    }

    let binding = app.state::<BackendProcess>();
    let mut guard = binding.0.lock().expect("backend process lock");
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }
    start_packaged_backend(&app).map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            app.manage(BackendProcess(Mutex::new(None)));
            if let Err(error) = start_packaged_backend(app.handle()) {
                // A slow or failed sidecar boot must not crash the client: the login
                // page renders its disconnected state and offers a reconnect button
                // backed by the `restart_backend` command.
                eprintln!("packaged SupportFlow backend not started yet: {error}");
            }
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![restart_backend])
        .build(tauri::generate_context!())
        .expect("error while building SupportFlow AI");
    app.run(|app, event| {
        if matches!(event, RunEvent::ExitRequested { .. }) {
            if let Some(process) = app.try_state::<BackendProcess>() {
                if let Some(mut child) = process.0.lock().expect("backend process lock").take() {
                    let _ = child.kill();
                }
            }
        }
    });
}
