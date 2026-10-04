# Changelog

รูปแบบอ้างอิง [Keep a Changelog](https://keepachangelog.com/) และ [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added
- **Nova → Knowledge Studio ใช้ service token ของ Nova เอง** (decision 1b = b, 2026-10-03)
  - `src/auth/service_token.py`: `ServiceTokenProvider` ขอ token (scope `knowledge:read`) จาก Identity Service ด้วย client credentials, แคชและต่ออายุก่อนหมดอายุ
  - `KnowledgeStudioClient` ใช้ token จาก provider อัตโนมัติ และเมื่อ Knowledge ตอบ 401 จะล้าง token แล้วลองใหม่ 1 ครั้ง
  - env ใหม่: `AUTH_TOKEN_URL`, `NOVA_CLIENT_ID`, `NOVA_CLIENT_SECRET` (ไม่มีค่า default ของ secret)
  - ต้องการให้ Identity Service อนุญาต `knowledge:read` ให้ client `nova-studio` (cloudforge-identity-service PR #1)

### Fixed
- `POST /query` ไม่ได้ส่ง token ไป Knowledge Studio เลย (Knowledge ที่บังคับ `knowledge:read` จะตอบ 401 และ Nova ตอบ 500) — เทสต์เดิมไม่เห็นเพราะ mock client ทั้งตัว
- ความล้มเหลวจาก Knowledge Studio ตอบ **502** และขอ service token ไม่ได้ตอบ **503** แทน 500 ที่ไม่ได้ดักไว้

## [0.2.0] - 2026-09-24

### Changed
- **Auth migration → Identity Contract v1 + cloudforge-auth-core v1.1.0**
  - ลบ `create_access_token()` และ HS256 local secret ออกทั้งหมด
  - เปลี่ยนมาใช้ RS256 + JWKS จาก Identity Service (ผ่าน `cloudforge-auth-core`)
  - บังคับ scope `nova:query` บน `POST /query` (403 เมื่อ scope ไม่พอ)
  - รองรับ 503 เมื่อ JWKS endpoint เข้าไม่ถึง
  - OpenAPI ประกาศ 401 + 403 (+ 503 แนะนำ) ครบตาม Foundation gate rule
- `.env.example` เปลี่ยนจาก `JWT_SECRET_KEY` → `AUTH_JWT_ISSUER` / `AUTH_JWT_AUDIENCE` / `AUTH_JWKS_URL`

### Removed
- `src/auth/jwt.py` (local encode/decode)
- Dependency `python-jose` (ย้ายไปอยู่ใน auth-core)

## [0.1.0] - Unreleased

### Added
- Scaffold repo ตาม Foundation Repository Standards Checklist ครบ
- Auth pattern มาตรฐาน (`src/auth/`) เหมือน Ingest Studio และ Knowledge Studio
- โครง RAG service: `LLMProvider` interface, `AnthropicProvider`, Knowledge Studio client, `POST /query` endpoint
- Docker Compose สำหรับรันในเครื่อง
