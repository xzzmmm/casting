# October 11 CastingNuwa demo package

[Download CastingNuwa_Oct11_Submission.zip](./CastingNuwa_Oct11_Submission.zip)

In GitHub's ZIP file view, choose **Download raw file** to save the archive.
Extract the ZIP before running the application.

## Run locally

Install Python 3.12. On Windows, open the extracted `CastingNuwa` folder and
double-click `start_demo_windows.bat`. The first run downloads dependencies,
so internet access is required. Keep the terminal open.

Alternatively, create and activate a virtual environment, then run:

```sh
python -m pip install -r requirements_demo.txt
python run_demo.py
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
`ea688dd500827b5d80b95d113ff1c5e5451aa1fa4730d8eb64929d8af4aa8edd`
