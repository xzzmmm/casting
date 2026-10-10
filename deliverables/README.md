# October 11 CastingNuwa demo package

[Download CastingNuwa_Oct11_Submission.zip](./CastingNuwa_Oct11_Submission.zip)

In GitHub's ZIP file view, choose **Download raw file** to save the archive.
Extract the ZIP before running the application.

## Run locally

Use an installed Python 3.10 or newer. On Windows, open the extracted `CastingNuwa` folder and
double-click `start_demo_windows.bat`. The first run downloads dependencies,
so internet access is required. Keep the terminal open.
The launcher now selects the installed default Python 3, including Python 3.13.
The full application checks were on Python 3.12; Windows/Python 3.13 still needs
verification on the presenting computer.

If you already extracted the earlier archive, download [the revised launcher](./start_demo_windows.bat)
and replace the file of the same name in your extracted application folder.

Alternatively, create and activate a virtual environment, then run:

```sh
python -m pip install -r requirements_demo.txt
python run_demo.py
```

For VS Code on a computer with Python 3.13, open the extracted application folder,
choose **Terminal → New Terminal**, then run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements_demo.txt
.\.venv\Scripts\python.exe run_demo.py
```

Open the local address printed by the runner (normally http://127.0.0.1:7860).
Full setup and demonstration instructions are in `SUBMISSION_README.md`.

## Contents and verified scope

The archive contains the refined Gradio application, minimal demo dependencies,
local sample-mode runner, individual journal, four-week project plan, solo progress
summary and validation record. Its code baseline is repository commit
`c48ddc8fe7bbf43221cfea707caa5bb96f4ad78f`, with the prepared UI/demo changes.

The sample text workflow was checked on Linux/Python 3.12: local HTTP 200,
150 UI components, 22 event bindings and 25 existing workflow assertions passed.
Real model quality, audio/video processing and the Windows launch helper were not
validated by those checks. Rehearse on the presenting computer before submission.

The archive retains the preparation-time status in its documents. This upload uses
the GitHub connection; it does not represent a Commit/Push in the student's GitHub
Desktop. Fetch/Pull in Desktop to sync this repository update.

Archive SHA-256:
`a4f60e9158de66a007e92bb759bef192e49aa3833bd2eaac164308f49e828d46`
