# MX/MH Zip Reassignment Tool

A tiny browser tool for manually assigning each MX/MH "filler zip" polygon to a
neighboring real zip code. Output is a CSV mapping `(filler_zip, poly_index) → real_zip`.

## For the coworker doing the assignments

You only need Python 3 (already installed on Mac and most Linux; on Windows
install from [python.org](https://www.python.org/downloads/)).

### Setup

1. Unzip the folder somewhere — e.g. `~/Desktop/mx-mh-mapping/`.
2. Open a terminal and `cd` into that folder:
   ```sh
   cd ~/Desktop/mx-mh-mapping
   ```
3. Start the local server:
   ```sh
   python3 -m http.server 8765
   ```
   (On Windows: `py -m http.server 8765`.)
   Leave this terminal window open the whole time you're working.
4. Open this URL in a browser: **http://localhost:8765/ui/**

### Using the tool

- The map shows one **red** polygon — that's the one to assign.
- **Yellow** polygons are other unassigned polygons in the same filler zip.
- **Blue** polygons are neighboring real zip codes — click one to assign the
  red polygon to it. The view advances to the next polygon automatically.
- Buttons / shortcuts:
  - `Skip` (`s`) — skip this polygon (record it as unassigned).
  - `Undo` (`u`) — clear the assignment for the current polygon.
  - `Prev` / `Next` (`p` / `n`) — move between polygons without changing them.
  - The dropdown at the top jumps to a different filler zip.
- Progress is **saved automatically** in your browser. You can close the tab
  and pick up later — but don't clear browser data, and try to use the same
  browser/profile each time.

### Exporting

Click **Export CSV** at any time to download a CSV of every assignment so far.
Send that file back when you're done (or periodically as a backup).

### Stopping

Close the browser tab and press `Ctrl+C` in the terminal to stop the server.

---

## For the maintainer (regenerating the data)

The `output/` folder is generated from the PostGIS database. To rebuild it:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python extract.py              # all MX/MH zips
.venv/bin/python extract.py --zip 890MX  # one zip (for smoke-testing)
```

The script reads `geography_zip_codes` from `postgresql://terramaps:terramaps@localhost:15433/app`
(override with `--dsn` or `$DATABASE_URL`).
