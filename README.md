# PyLoader

PyLoader is a password-protected cloud audio workspace. It searches YouTube videos, queues MP3 conversion, and lets signed-in users download results from phones, tablets, and desktops.

## Deploy on Render
1. In Render, choose **New → Blueprint** and connect this repository.
2. Select `render.yaml` at the repository root.
3. Set the required `ACCESS_PASSWORD` to a strong private password.
4. Deploy and open the HTTPS URL on any device.

The Render service uses the paid Starter plan. Confirm current provider pricing before deploying. Source code on GitHub is not a live hosted service until deployment is completed.

## Important
Use this only for content you own or are authorized to download. Respect YouTube's terms and copyright. The app does not bypass DRM, private-video restrictions, or other access controls.

MP3 files are temporary and cleaned after roughly six hours; they are not a permanent cloud music library. Access uses one shared password. Do not publish it. Search is rate-limited per IP. For larger public use, add managed storage, individual accounts, quotas, abuse controls, and a persistent job queue.

## Local development
Requires Python 3.12+ and FFmpeg.

```bash
python -m venv .venv
pip install -r requirements.txt
```

Set `APP_SECRET` and `ACCESS_PASSWORD`, then run `python app.py`. Open http://127.0.0.1:8080.
