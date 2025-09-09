# textsearch
Claude Sonnet 4 generated from prompt:

```create an app or script that runs on Windows.  It takes a list of texts as input and a folder.  It recursively searches the folder for all occurrences of those texts.  If any folder has a .gitignore file, for that folder skip its files and subfolders specified by the .gitignore, except always search files named ".env".  Do not search binary files.```

Put textsearch.py and textsearch.bat in a directory such as C:\MyScripts, and add that directory to your Path.

The batch wrapper ensures that:

- You don't need to type python before the script name
- The script runs from its original location
- Arguments are passed through correctly

### Key Features:

- **Text Search:** Takes multiple search terms as input and finds all occurrences
- **Recursive Directory Search:** Searches through all subdirectories
- **.gitignore Support:** Respects .gitignore rules in each directory
- **.env Exception:** Always searches .env files regardless of .gitignore
- **Binary File Detection:** Automatically skips binary files using multiple heuristics
- **Cross-platform:** Works on Windows, macOS, and Linux

#### Basic usage:

`textsearch "TODO" "FIXME" -d "C:\path\to\your\project"`

#### Search current directory:

`textsearch "password" "secret"`

#### Save results to file:

`textsearch "import pandas" -d . -o results.txt`

#### Case-sensitive search:

`textsearch "myVariable" --case-sensitive -d ./src`

### Features in Detail:

- **Smart .gitignore handling:** Finds and parses all .gitignore files in the directory tree
- **Pattern matching:** Supports glob patterns, directory patterns, and negation patterns
- **Binary detection:** Uses MIME types and content analysis to skip binary files
- **Progress feedback:** Shows progress for large directory trees
- **Error handling:** Gracefully handles permission errors and unreadable files
- **Flexible output:** Console output or save to file
