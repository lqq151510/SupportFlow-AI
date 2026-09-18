import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const backendDir = join(rootDir, 'backend');
const outputDir = join(backendDir, 'target', 'desktop');
const inputDir = join(backendDir, 'target', 'desktop-input');
const runtimeDir = join(backendDir, 'target', 'desktop-runtime');
const appName = 'SupportFlowBackend';
const jarName = 'supportflow-backend-0.0.1-SNAPSHOT.jar';
const isWindows = process.platform === 'win32';
const executable = (name) => isWindows ? `${name}.exe` : name;
const maven = isWindows ? 'mvn.cmd' : 'mvn';
const javaHomeBin = process.env.JAVA_HOME ? join(process.env.JAVA_HOME, 'bin') : null;
const javaTool = (name) => javaHomeBin && existsSync(join(javaHomeBin, executable(name)))
  ? join(javaHomeBin, executable(name))
  : executable(name);
const run = (command, args, options = {}) => {
  const executableCommand = isWindows && command.endsWith('.cmd')
    ? [process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', command, ...args]]
    : [command, args];
  return execFileSync(executableCommand[0], executableCommand[1], {
    cwd: backendDir,
    stdio: 'inherit',
    ...options,
  });
};

run(maven, ['-B', '-DskipTests', 'package']);

rmSync(inputDir, { recursive: true, force: true });
rmSync(runtimeDir, { recursive: true, force: true });
rmSync(join(outputDir, isWindows ? appName : `${appName}.app`), { recursive: true, force: true });
mkdirSync(inputDir, { recursive: true });
copyFileSync(join(backendDir, 'target', jarName), join(inputDir, jarName));

const moduleOutput = execFileSync(javaTool('java'), ['--list-modules'], { encoding: 'utf8' });
const modules = moduleOutput.trim().split(/\r?\n/).map((line) => line.split('@')[0]).join(',');
run(javaTool('jlink'), [
  '--add-modules', modules,
  '--strip-debug',
  '--no-header-files',
  '--no-man-pages',
  '--compress=zip-6',
  '--output', runtimeDir,
]);

// jpackage requires the first version component to be at least 1. The helper
// process is internal; the user-facing version comes from tauri.conf.json.
run(javaTool('jpackage'), [
  '--type', 'app-image',
  '--name', appName,
  '--input', inputDir,
  '--main-jar', jarName,
  '--runtime-image', runtimeDir,
  '--dest', outputDir,
  '--app-version', '1.0.0',
]);
