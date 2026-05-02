#!/usr/bin/env node

const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const readline = require('readline');
const { execFileSync } = require('child_process');

const API_URL = process.env.GENERATOR_API_URL || 'http://127.0.0.1:8000';

function getArg(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) return null;
  return process.argv[index + 1] || null;
}

function hasFlag(name) {
  return process.argv.includes(name);
}

function decodeConfig(token) {
  const padded = token.padEnd(token.length + ((4 - (token.length % 4)) % 4), '=');
  return JSON.parse(Buffer.from(padded, 'base64url').toString('utf-8'));
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

function ask(question, defaultValue) {
  const suffix = defaultValue ? ` (${defaultValue})` : '';
  return new Promise((resolve) => {
    rl.question(`${question}${suffix}: `, (answer) => {
      resolve(answer.trim() || defaultValue);
    });
  });
}

function requestJson(method, url, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const payload = body ? JSON.stringify(body) : null;
    const request = http.request(
      {
        method,
        hostname: parsed.hostname,
        port: parsed.port,
        path: `${parsed.pathname}${parsed.search}`,
        headers: {
          'Content-Type': 'application/json',
          ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
        },
      },
      (response) => {
        let data = '';
        response.on('data', (chunk) => {
          data += chunk;
        });
        response.on('end', () => {
          if (response.statusCode >= 400) {
            reject(new Error(data || `HTTP ${response.statusCode}`));
            return;
          }
          resolve(data ? JSON.parse(data) : {});
        });
      },
    );

    request.on('error', reject);
    if (payload) request.write(payload);
    request.end();
  });
}

function downloadFile(url, destination) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destination);
    http
      .get(url, (response) => {
        if (response.statusCode >= 400) {
          reject(new Error(`No se pudo obtener el proyecto: HTTP ${response.statusCode}`));
          return;
        }
        response.pipe(file);
        file.on('finish', () => {
          file.close(resolve);
        });
      })
      .on('error', reject);
  });
}

async function promptConfig() {
  const projectName = await ask('Nombre del proyecto', 'mi-proyecto-base');
  const description = await ask('Descripcion breve', 'Arquitectura base generada para iniciar desarrollo rapidamente.');
  const projectProfile = await ask('Perfil [standard|ai|microservices|api-only]', 'standard');
  const auth = await ask('Autenticacion [firebase|none]', 'firebase');
  const database = await ask('Base de datos [postgresql|firestore|none]', 'postgresql');
  const cloud = await ask('Cloud [local|gcp|aws|azure]', 'local');
  const targetOs = await ask('Sistema operativo [mac|windows]', process.platform === 'win32' ? 'windows' : 'mac');
  const includeServices = await ask('Incluir microservicio base [yes|no]', 'no');

  return {
    project_name: projectName,
    description,
    project_profile: projectProfile,
    project_type: projectProfile === 'api-only' ? 'api' : 'fullstack',
    frontend: 'react',
    backend: 'fastapi',
    auth,
    database,
    cloud,
    containers: database === 'postgresql' ? ['frontend', 'backend', 'database'] : ['frontend', 'backend'],
    include_docker: true,
    include_dev_script: true,
    include_services: includeServices.toLowerCase().startsWith('y'),
    target_os: targetOs,
  };
}

function extractProject(archivePath, outputDir) {
  if (process.platform === 'win32') {
    execFileSync(
      'powershell',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', `Expand-Archive -Path "${archivePath}" -DestinationPath "${outputDir}" -Force`],
      { stdio: 'inherit' },
    );
    return;
  }
  execFileSync('unzip', ['-oq', archivePath, '-d', outputDir], { stdio: 'inherit' });
}

function runSetup(projectDir) {
  if (fs.existsSync(path.join(projectDir, 'dev.ps1')) && process.platform === 'win32') {
    execFileSync('powershell', ['-ExecutionPolicy', 'Bypass', '-File', 'dev.ps1', 'setup'], { cwd: projectDir, stdio: 'inherit' });
    return;
  }

  if (fs.existsSync(path.join(projectDir, 'dev.sh'))) {
    execFileSync('chmod', ['+x', 'dev.sh', 'setup.sh'], { cwd: projectDir, stdio: 'inherit' });
    execFileSync('./dev.sh', ['setup'], { cwd: projectDir, stdio: 'inherit' });
  }
}

async function main() {
  console.log('Reference Architecture Generator');
  console.log(`API: ${API_URL}`);
  console.log('');

  try {
    await requestJson('GET', `${API_URL}/health`);
  } catch (error) {
    console.error('No pude conectar con el backend generador.');
    console.error('Levanta la plataforma con: ./dev.sh start');
    process.exit(1);
  }

  const configToken = getArg('--config');
  const config = configToken ? decodeConfig(configToken) : await promptConfig();
  rl.close();

  const result = await requestJson('POST', `${API_URL}/generate`, config);
  const tempArchive = path.join(os.tmpdir(), result.file_name);
  await downloadFile(`${API_URL}${result.download_url}`, tempArchive);
  extractProject(tempArchive, process.cwd());
  fs.rmSync(tempArchive, { force: true });

  const projectDir = path.resolve(process.cwd(), config.project_name);
  if (fs.existsSync(path.join(projectDir, 'dev.sh'))) {
    execFileSync('chmod', ['+x', 'dev.sh', 'setup.sh'], { cwd: projectDir, stdio: 'inherit' });
  }

  if (hasFlag('--install')) {
    runSetup(projectDir);
  }

  console.log('');
  console.log(`Proyecto creado en: ${projectDir}`);
  console.log('Para levantarlo:');
  console.log(`  cd ${config.project_name}`);
  console.log(config.target_os === 'windows' ? '  .\\dev.ps1 start' : '  ./dev.sh start');
}

main().catch((error) => {
  rl.close();
  console.error(error.message);
  process.exit(1);
});
