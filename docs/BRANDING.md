# Shared Notes artwork

The editable mark and icon geometry belong to LamaStart-UI's shared LamaUI
catalogue. Import one verified source revision with:

```powershell
python scripts/build-pwa-icons.py --source-root C:/Users/thoma/Desktop/work/LamaStart-UI/frontend/src/assets/lamaui
```

The importer uses the shared `export-web-brand.py` helper and updates the home
mark, versioned PWA icons, favicon aliases and Windows ICO together. The PWA
keeps its identity, scope, launch target, sharing and file handlers. Old hashed
icon files stay available for already installed clients. Consumer files are
bundled into the ordinary Notes release, with no extra runtime dependency.

The foreground is centered from its meaningful alpha bounds. Normal icons and
the native Android shortcuts share the same visible fit. Maskable icons use a
separate safe-radius export. `client/assets/brand/lamaui-source.json` records
the imported revision and source hash without local paths or account data.
