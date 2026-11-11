# Voyaura Web

Responsive Vue 3 PWA for Voyaura's map-first travel experience.

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

The app keeps a usable China-atlas fallback when AMap credentials are absent.
Set `VITE_AMAP_KEY` and `VITE_AMAP_SECURITY_CODE` in `.env.local` to load AMap
JS API 2.0. The API defaults to `http://127.0.0.1:8001/api/v1`.
