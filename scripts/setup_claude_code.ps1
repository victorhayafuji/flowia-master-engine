# FlowIA - setup Claude Code (extensao Cursor + CLI)
# Uso: powershell -ExecutionPolicy Bypass -File scripts/setup_claude_code.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "FlowIA - Claude Code setup" -ForegroundColor Cyan
Write-Host "Repo: $Root"
Write-Host ""

# 1. MCP para Claude Code (.mcp.json na raiz)
$cursorMcp = Join-Path $Root ".cursor\mcp.json"
$claudeMcp = Join-Path $Root ".mcp.json"
$example = Join-Path $Root ".mcp.json.example"

if (Test-Path $cursorMcp) {
    Copy-Item $cursorMcp $claudeMcp -Force
    Write-Host "[OK] MCP sincronizado: .cursor/mcp.json -> .mcp.json" -ForegroundColor Green
}
elseif (Test-Path $claudeMcp) {
    Write-Host "[OK] .mcp.json ja existe" -ForegroundColor Green
}
else {
    Copy-Item $example $claudeMcp
    Write-Host "[!] Criado .mcp.json a partir do example - edite YOUR_PROJECT_REF e YOUR_RENDER_API_KEY" -ForegroundColor Yellow
}

# 2. CLI (opcional)
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    $ver = & claude --version 2>&1
    Write-Host "[OK] CLI: $ver" -ForegroundColor Green
    $authJson = & claude auth status 2>&1 | Out-String
    if ($authJson -match '"loggedIn":\s*true') {
        Write-Host "[OK] CLI autenticado" -ForegroundColor Green
    }
    else {
        Write-Host "[!] CLI nao autenticado - rode: claude auth login" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[!] CLI nao encontrado - npm i -g @anthropic-ai/claude-code" -ForegroundColor Yellow
}

# 3. Extensao Cursor
$cursor = Get-Command cursor -ErrorAction SilentlyContinue
if ($cursor) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $extList = & cursor --list-extensions 2>$null
    $ErrorActionPreference = $prevEap
    if ($extList -match "anthropic\.claude-code") {
        Write-Host "[OK] Extensao anthropic.claude-code instalada no Cursor" -ForegroundColor Green
    }
    else {
        Write-Host "[!] Instale: cursor --install-extension anthropic.claude-code" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Proximos passos (manual):" -ForegroundColor Cyan
Write-Host "  1. Cursor: icone Spark (Claude Code) -> login Anthropic Pro"
Write-Host "  2. Terminal (opcional): claude auth login"
Write-Host "  3. Teste: Leia CLAUDE.md Partes I-VII; nao implementar Parte VIII"
Write-Host "  4. Cursor Agent e Claude Code NAO compartilham contexto - reabra o escopo em cada sessao"
