# Replit handoff

## What is ready

This repository now includes `.replit` and `replit_start.sh`. The configured path installs the locked frontend dependencies when needed, builds the Vite frontend, and starts FastAPI on `0.0.0.0` using `${PORT:-8000}`. The repository's `/health`, `/ready`, smoke gate, and runtime benchmark are the checks to run after import.

## Import

1. Open the GitHub import flow at <https://replit.com/import>.
2. Choose GitHub and import `akameredon/ink-flow-handwriting-studio` from `main`.
3. Let Replit install dependencies and use the committed `.replit` configuration.
4. If the importer asks for a run command, use `bash replit_start.sh`.
5. Run the app and confirm the Preview responds at `/health` and `/ready`.

Replit's official import documentation says repository files and dependency configuration are imported, while existing secret values and platform-specific services are not. This repository deliberately contains no secret values.

## Preview verification

From the Replit Shell, run:

```bash
python scripts/smoke_deployment.py --base-url "$REPLIT_DEV_DOMAIN"
python scripts/benchmark_runtime.py --base-url "$REPLIT_DEV_DOMAIN" --requests 5 --concurrency 2 --json > preview-runtime.json
```

If the shell cannot resolve the development domain, use the Preview URL shown by Replit and pass its reachable base URL instead. Confirm the browser journey at narrow mobile, tablet, and desktop widths, then check keyboard navigation, visible focus, screen-reader labels, contrast, reduced motion, error states, and PDF download.

## Optional handwriting provider

Do not enable this for the first core lesson/PDF launch unless it is explicitly approved. If a local provider is approved, add only the required values through Replit's Secrets/Configurations tool, never into GitHub or browser code. Typical settings are:

```text
HTR_PROVIDER=kraken
HTR_KRAKEN_MODEL=/path/to/provisioned/model.mlmodel
HTR_KRAKEN_DEVICE=cpu
```

The model file must be provisioned through an approved deployment process. The application does not download a model implicitly. Run the real-data validation CLI only with a consented, human-transcribed manifest and `real_data: true`.

## Publish and rollback

Use Replit Preview first. Publish only after the preview smoke gate and runtime benchmark pass. Replit's publishing flow creates a separate stable deployment, supports access-level selection, security checks, monitoring, and a later republish workflow. Record the published URL, release identifier, observed CPU/memory/latency, and the previous known-good commit before public launch.

Rollback means returning the deployment to the last verified release, then rerunning the smoke gate against the live URL. Do not treat a successful Preview as a production release or as handwriting-accuracy evidence.

## What Replit can and cannot finish

Replit can import the repository, install dependencies, run the service, provide a Preview, perform manual browser validation, store deployment secrets, publish the core application, and expose deployment monitoring. Its Agent App Testing documentation currently describes support for Full Stack JavaScript and Streamlit Python applications; this FastAPI/Vite project should therefore use ordinary Preview/manual browser checks unless Replit confirms broader support in the account.

Replit cannot create a real teacher-labelled handwriting dataset, replace human transcription, certify CER/WER or teacher acceptance, approve the HTR provider/resource budget, perform a human release sign-off, or authorize a public launch on the owner's behalf.

## Handoff decision

The recommended first Replit release is the core curriculum, lesson-note, and printable-PDF application. Keep natural-page handwriting analysis experimental and gated until real labelled data, target-host measurements, accessibility/device evidence, rollback evidence, and explicit project-owner approval are recorded.

Official Replit references:

- GitHub import: <https://docs.replit.com/build/import-from-providers>
- Project configuration: <https://docs.replit.com/features/project-setup/configuration>
- Secrets: <https://docs.replit.com/core-concepts/project-editor/app-setup/secrets>
- Publishing and monitoring: <https://docs.replit.com/build/publish-your-app>
- App Testing limitations: <https://docs.replit.com/features/agent/app-testing>
