use base64::{engine::general_purpose::STANDARD, Engine as _};
use rand::RngCore;
use std::{fs, process::{Child, Command}, sync::Mutex, thread, time::Duration};
use tauri::{Manager, RunEvent};

const KEYCHAIN_SERVICE: &str = "com.lqq.supportflow.model-secret.v1";
const KEYCHAIN_ACCOUNT: &str = "MODEL_SECRET_MASTER_KEY";

struct BackendProcess(Mutex<Option<Child>>);

fn backend_is_healthy() -> bool {
  Command::new("curl")
    .args(["--fail", "--silent", "http://localhost:8080/actuator/health"])
    .status()
    .is_ok_and(|status| status.success())
}

fn model_secret() -> Result<String, String> {
  let existing = Command::new("security")
    .args(["find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w"])
    .output()
    .map_err(|error| format!("cannot read macOS Keychain: {error}"))?;
  if existing.status.success() {
    return String::from_utf8(existing.stdout).map(|value| value.trim().to_owned()).map_err(|error| error.to_string());
  }

  let mut bytes = [0_u8; 32];
  rand::rng().fill_bytes(&mut bytes);
  let generated = STANDARD.encode(bytes);
  let status = Command::new("security")
    .args(["add-generic-password", "-U", "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w", &generated])
    .status()
    .map_err(|error| format!("cannot save local model key in macOS Keychain: {error}"))?;
  if !status.success() { return Err("cannot save local model key in macOS Keychain".into()); }
  Ok(generated)
}

fn start_packaged_backend(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
  if cfg!(debug_assertions) { return Ok(()); }
  if backend_is_healthy() { return Ok(()); }

  let data_dir = app.path().app_data_dir()?;
  fs::create_dir_all(data_dir.join("data"))?;
  fs::create_dir_all(data_dir.join("logs"))?;
  let backend = app.path().resource_dir()?.join("SupportFlowBackend.app/Contents/MacOS/SupportFlowBackend");
  let mut child = Command::new(backend)
    .env("MODEL_SECRET_MASTER_KEY", model_secret().map_err(std::io::Error::other)?)
    .env("SUPPORTFLOW_DESKTOP_DATA_DIR", data_dir.join("data"))
    .env("SUPPORTFLOW_MODEL_MOCK_ENABLED", "false")
    .arg("--spring.profiles.active=desktop")
    .stdout(fs::File::create(data_dir.join("logs/backend.out.log"))?)
    .stderr(fs::File::create(data_dir.join("logs/backend.err.log"))?)
    .spawn()?;
  for _ in 0..40 {
    if backend_is_healthy() {
      *app.state::<BackendProcess>().0.lock().expect("backend process lock") = Some(child);
      return Ok(());
    }
    if child.try_wait()?.is_some() {
      return Err("packaged SupportFlow backend exited before becoming healthy".into());
    }
    thread::sleep(Duration::from_millis(250));
  }
  let _ = child.kill();
  return Err("packaged SupportFlow backend did not become healthy within 10 seconds".into());
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .setup(|app| {
      app.manage(BackendProcess(Mutex::new(None)));
      start_packaged_backend(app)?;
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
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
