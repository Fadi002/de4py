# Contributing to De4py Localization

We welcome contributions to make De4py accessible to everyone! Adding a new language or updating an existing one is straightforward.

## Translation System Overview

De4py uses a JSON-based translation system located in `de4py/lang/locales/`. 
Each language has its own `.json` file named after its ISO 639-1 code (e.g., `en.json`, `es.json`, `ar.json`).

The system automatically detects new language files in this directory.

## How to Add a New Language

1.  **Find the Language Code**: Identify the ISO 639-1 code for your language (e.g., `fr` for French, `de` for German, `ja` for Japanese).
2.  **Create the File**: Create a new file in `de4py/lang/locales/` named `<code.json>`.
3.  **Add Metadata**: Start the file with the required metadata:
    ```json
    {
        "LANG_NAME": "Français",
        "IS_RTL": false,
        ...
    }
    ```
    - `LANG_NAME`: The name of the language as it should appear in the settings menu (in native script).
    - `IS_RTL`: Set to `true` if the language is Right-to-Left (like Arabic or Hebrew), otherwise `false`.


4.  **Copy Keys**: Copy the content from `en.json` (English) into your new file.
5.  **Translate values**: Translate the values (right side) into your language. **Do not change the keys (left side).**

    *Example:*
    ```json
    "nav.home": "Accueil",
    "common.btn.save": "Enregistrer"
    ```

6.  **Test**: 
    - Open De4py.
    - Go to **Settings**.
    - Select your new language from the dropdown.
    - Verify that text appears correctly and layout is correct.

## How to Update Existing Translations

1.  Open the relevant `.json` file in `de4py/lang/locales/`.
2.  Find the key you want to update.
3.  Change the text value.
4.  Save and restart the app (or switch languages) to see changes.

## Placeholders and Plurals

### Placeholders
Some strings contain placeholders like `{name}` or `{count}`. **Keep these exactly as they are** in the translated string.

*English:* `"Hello {name}!"`
*French:* `"Bonjour {name} !"`

### Plurals
We support pluralization for keys starting with `plural.`. These keys map to an object containing different forms based on the count.

Supported forms (based on CLDR):
- `zero`, `one`, `two`, `few`, `many`, `other`

*Example:*
```json
"plural.files": {
    "one": "{count} fichier",
    "other": "{count} fichiers"
}
```
At minimum, `other` is required. `one` is highly recommended.

## Community Platforms

We use [Crowdin](https://crowdin.com/project/de4py) for translations.  
.

You can export the JSON files from these platforms and place them in the `locales` folder.
