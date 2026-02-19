# ComicSaver

A robust, Selenium-based command-line tool designed to scrape and download high-quality comic images from `readcomiconline.li`. It handles Cloudflare protection, JavaScript-rendered content, and lazy-loading images automatically.

## Features

- **Bypasses Protection**: Uses Selenium with headless Chrome to handle Cloudflare and dynamic JavaScript.
- **Smart Scrolling**: Implements an "incremental scrolling with patience" algorithm to ensure all lazy-loaded images are captured, even on slow connections.
- **Organized Output**: Automatically creates a structured directory hierarchy: `Output/ComicName/IssueName/`.
- **Flexible**: Scrape a single issue or an entire comic series (work in progress for full series recursion, currently optimized for single issues).
- **Headless Mode**: Runs silently in the background by default.

## Prerequisites

- Python 3.8+
- [Google Chrome](https://www.google.com/chrome/) installed on your machine.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd comicsaver
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `selenium`, `webdriver-manager`, `requests`, and `beautifulsoup4`.

## Usage

Run the script from the root directory using Python:

```bash
python src/scraper.py [URL] [OPTIONS]
```

### Arguments

- `URL`: The URL of the comic issue or main page (e.g., `https://readcomiconline.li/Comic/JLA-Avengers/Issue-1`).
- `-o`, `--output`: (Optional) The directory to save downloaded comics. Defaults to `Comics`.
- `--headless`: (Optional) Run the browser in headless mode (no UI). Useful for background tasks.

### Examples

**Download a specific issue:**

```bash
python src/scraper.py "https://readcomiconline.li/Comic/JLA-Avengers/Issue-1" -o MyComics --headless
```

**Download with visible browser (for debugging):**

```bash
python src/scraper.py "https://readcomiconline.li/Comic/JLA-Avengers/Issue-1"
```

## Project Structure

```
comicsaver/
├── src/
│   └── scraper.py       # Main scraper script logic
├── requirements.txt     # Python dependencies
├── .gitignore           # Git ignore rules
└── README.md            # Project documentation
```

## Troubleshooting

- **"No images found"**: Ensure your internet connection is stable. The script waits for images to load, but extremely slow connections might timeout.
- **Chrome driver errors**: The `webdriver-manager` should handle driver installation automatically. If it fails, try upgrading it: `pip install --upgrade webdriver-manager`.
