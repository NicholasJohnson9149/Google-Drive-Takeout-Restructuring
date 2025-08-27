# Google Takeout Restructure Tool — Product Plan

This document outlines the plan for building the **Google Takeout Restructure Tool** with a **desktop GUI** that connects seamlessly to our **CLI tooling**. The goal is to let users select Google Takeout ZIPs, configure settings, choose an output location, and restructure their files reliably.

![Main Home Screen for UI](<imgs/01 Google Drive Tackout Restructuring - App.png>)

## **1. Core User Flow**

1. **Download & Launch**
   - Users download the app from GitHub as a standalone executable (`.dmg` / `.exe`).
   - On launch, the GUI server starts locally and opens the application.

2. **Select Takeout Files**
   - On the homepage, users click **"Select"** to pick the folder containing Google Takeout ZIP files.
   - **Key constraint:** No hard-coded paths — fully dynamic file selection.

3. **Set Preferences**
   - Options available:
     - **Dry Run** → Simulates the process without modifying files.
     - **Duplicate Checking** → Ensures 1o duplicate files are created.
     - **Verification** → Performs checksum validation post-restructure.

4. **Select Output Directory**
   - Users choose where the restructured files will be stored:
     - Local disk
     - External hard drive
   - Again, **no hard-coded paths**.

5. **Start Reconstruction**
   - Clicking **"Start"** triggers the CLI process with the selected paths and flags.
   - CLI tool executes restructuring logic beneath the GUI.

---

![alt text](<imgs/03 Google Drive Tackout Restructuring - Processing Progress Screen.png>)

## **2. Progress & Feedback**

Once started, the GUI transitions to a **progress dashboard**:

- **Estimated Time Remaining**: Dynamically calculated.
- **Progress Bar**: Percentage complete.
- **Current Task**:
  - Extracting Takeout ZIPs.
  - Storing temporary files.
  - Restructuring folders.
- **Steps Completed vs. Remaining**.

### **Features**
- **Cancelable Process** → Users can stop mid-process.
- **Persistence on Refresh** → If the app closes or tab reloads, the progress view restores from the server state.
- **Single Task Limitation** → Only one active reconstruction allowed at a time.

---

![alt text](<imgs/04 Google Drive Tackout Restructuring - Completed Screen.png>)

## **3. Completion & Results**

After successful completion:

- Display:
  - **Total Files Processed**
  - **Total Data Size**
  - **Restructure Summary**
- Provide:
  - A clickable **"Open Output Folder"** button.
  - Downloadable **process logs** for debugging or record-keeping.

---

## **4. Technical Architecture**

### **Frontend (GUI)**
- **Framework:** React or Svelte (lean, desktop-friendly)
- **Desktop Packaging:** Tauri or Electron (Tauri preferred for speed/size)
- **Features:**
  - Dynamic file selection via OS dialogs.
  - Persistent state for long-running processes.

### **Backend**
- **Local Server:** Lightweight FastAPI or Node-based server.
- **Responsibilities:**
  - Orchestrates CLI calls.
  - Streams progress updates via WebSockets.
  - Stores temporary state for persistence.

### **CLI Integration**
- Flags mirror GUI options:
  ```bash
  restructure-takeout \
    --input "/path/to/takeout" \
    --output "/path/to/output" \
    --dry-run \
    --check-duplicates \
    --verify