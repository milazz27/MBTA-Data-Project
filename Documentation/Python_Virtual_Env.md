# Python Virtual Environment Guide

This project uses a Python virtual environment to keep project dependencies separate from the system Python installation.

## First-Time Setup

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install python-dotenv
```

Install any additional project dependencies as needed.

---

## Starting Work on the Project

1. Open a terminal.
2. Navigate to the project directory:

```bash
cd "/mnt/c/Users/milen/MBTA/MBTA Data Project/Python Scripts"
```

3. Activate the virtual environment:

```bash
source .venv/bin/activate
```

You should see `(.venv)` at the beginning of the command prompt:

```bash
(.venv) ilatila@milaspc:~/...
```

This indicates that the virtual environment is active.

---

## Installing New Packages

With the virtual environment activated:

```bash
pip install package-name
```

Example:

```bash
pip install pandas requests beautifulsoup4
```

---

## Saving Dependencies

If you install new packages, update the requirements file:

```bash
pip freeze > requirements.txt
```

---

## Restoring Dependencies

After cloning the project on a new machine:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Leaving the Virtual Environment

When you are finished working:

```bash
deactivate
```

The `(.venv)` prefix will disappear from the terminal prompt, indicating you have returned to the system Python environment.

---

## Quick Reference

Activate:

```bash
source .venv/bin/activate
```

Check active environment:

```bash
which python
```

Leave environment:

```bash
deactivate
```

Update requirements:

```bash
pip freeze > requirements.txt
```