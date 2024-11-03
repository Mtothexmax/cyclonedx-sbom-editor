import json
import sys
from js import document, File, window, Uint8Array, Blob, console, FileReader, Event
from pyodide.ffi import create_proxy, to_js
from io import BytesIO

# Hide loading overlay once PyScript is ready
loading_elem = document.getElementById("loading")
loading_elem.style.display = "none"

# Global variable to track current conversion direction
conversion_direction = "spdx-to-cdx"


def debug_print(message):
    debug_elem = document.getElementById("debug")
    current = debug_elem.innerHTML
    debug_elem.innerHTML = current + "\n" + str(message)
    debug_elem.scrollTop = debug_elem.scrollHeight
    console.log(message)


def is_valid_spdx(json_data):
    try:
        required_fields = ["spdxVersion", "dataLicense", "SPDXID"]
        return all(field in json_data for field in required_fields)
    except Exception as e:
        debug_print(f"Error in SPDX validation: {str(e)}")
        return False


def is_valid_cyclonedx(json_data):
    try:
        required_fields = ["bomFormat", "specVersion", "version"]
        return (
            all(field in json_data for field in required_fields)
            and json_data["bomFormat"] == "CycloneDX"
        )
    except Exception as e:
        debug_print(f"Error in CycloneDX validation: {str(e)}")
        return False


def convert_spdx_to_cyclonedx(spdx_data):
    debug_print("Converting SPDX to CycloneDX...")
    cyclonedx = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "components": [],
    }
    if "packages" in spdx_data:
        for pkg in spdx_data["packages"]:
            component = {
                "type": "library",
                "name": pkg.get("name", ""),
                "version": pkg.get("versionInfo", ""),
            }
            if "licenseConcluded" in pkg:
                component["licenses"] = [{"license": {"id": pkg["licenseConcluded"]}}]
            if "supplier" in pkg:
                component["supplier"] = {"name": pkg["supplier"]}
            cyclonedx["components"].append(component)
    return cyclonedx


def convert_cyclonedx_to_spdx(cyclonedx_data):
    debug_print("Converting CycloneDX to SPDX...")
    spdx = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Converted-from-CycloneDX",
        "packages": [],
    }
    if "components" in cyclonedx_data:
        for comp in cyclonedx_data["components"]:
            package = {
                "name": comp.get("name", ""),
                "versionInfo": comp.get("version", ""),
                "SPDXID": f"SPDXRef-Package-{comp.get('name', '').replace(' ', '-')}",
            }
            if "licenses" in comp and comp["licenses"]:
                package["licenseConcluded"] = (
                    comp["licenses"][0].get("license", {}).get("id", "NOASSERTION")
                )
            if "supplier" in comp:
                package["supplier"] = comp["supplier"].get("name", "")
            spdx["packages"].append(package)
    return spdx


def show_status(message, is_error=False):
    status_elem = document.getElementById("status")
    status_elem.innerHTML = message
    status_elem.className = "error" if is_error else "success"
    debug_print(f"Status: {message}")


def create_download_link(data):
    try:
        json_str = json.dumps(data, indent=2)
        blob = Blob.new([json_str], {type: "application/json"})
        url = window.URL.createObjectURL(blob)
        download_btn = document.getElementById("download-btn")

        def download_handler(e):
            a = document.createElement("a")
            a.href = url
            a.download = "cyclonedx-sbom.json"
            a.click()

        download_btn.onclick = create_proxy(download_handler)
        download_btn.style.display = "block"
        debug_print("Download link created successfully")
    except Exception as e:
        debug_print(f"Error creating download link: {str(e)}")
        show_status(f"Error creating download link: {str(e)}", True)


def handle_file_content(content):
    try:
        json_data = json.loads(content)
        if conversion_direction == "spdx-to-cdx":
            if not is_valid_spdx(json_data):
                show_status("Invalid SPDX format. Please check your input file.", True)
                return
            converted_data = convert_spdx_to_cyclonedx(json_data)
        else:
            if not is_valid_cyclonedx(json_data):
                show_status(
                    "Invalid CycloneDX format. Please check your input file.", True
                )
                return
            converted_data = convert_cyclonedx_to_spdx(json_data)
        show_status("Conversion successful! Click the button below to download.")
        create_download_link(converted_data)
    except Exception as e:
        debug_print(f"Error processing content: {str(e)}")
        show_status(f"Error processing content: {str(e)}", True)


async def handle_file(event):
    try:
        file = event.target.files.item(0)
        if not file:
            return
        debug_print(f"Processing file: {file.name}")
        reader = FileReader.new()

        def onload(e):
            content = e.target.result
            handle_file_content(content)

        reader.onload = create_proxy(onload)
        reader.readAsText(file)
    except Exception as e:
        debug_print(f"Error in handle_file: {str(e)}")
        show_status(f"Error processing file: {str(e)}", True)


def toggle_conversion_direction(direction):
    global conversion_direction
    conversion_direction = direction
    # Update UI
    spdx_to_cdx = document.getElementById("spdx-to-cdx")
    cdx_to_spdx = document.getElementById("cdx-to-spdx")
    if direction == "spdx-to-cdx":
        spdx_to_cdx.className = "toggle-btn active"
        cdx_to_spdx.className = "toggle-btn"
    else:
        spdx_to_cdx.className = "toggle-btn"
        cdx_to_spdx.className = "toggle-btn active"
    # Reset UI state
    document.getElementById("status").innerHTML = ""
    document.getElementById("download-btn").style.display = "none"
    document.getElementById("file-input").value = ""
    # Update drop zone text
    drop_zone = document.getElementById("drop-zone")
    input_format = "SPDX" if direction == "spdx-to-cdx" else "CycloneDX"
    drop_zone.querySelector("p").innerHTML = (
        f"Drag and drop your {input_format} file here or"
    )


# Set up event listeners
file_input = document.getElementById("file-input")
file_input.onchange = create_proxy(handle_file)

# Setup conversion direction toggle buttons
spdx_to_cdx = document.getElementById("spdx-to-cdx")
cdx_to_spdx = document.getElementById("cdx-to-spdx")
spdx_to_cdx.onclick = create_proxy(lambda e: toggle_conversion_direction("spdx-to-cdx"))
cdx_to_spdx.onclick = create_proxy(lambda e: toggle_conversion_direction("cdx-to-spdx"))


# Setup debug panel toggle
def toggle_debug(e):
    debug_container = document.querySelector(".debug-container")
    if "expanded" in debug_container.className:
        debug_container.className = "debug-container"
    else:
        debug_container.className = "debug-container expanded"


debug_header = document.querySelector(".debug-header")
debug_header.onclick = create_proxy(toggle_debug)


# Drag and drop handlers
def handle_dragover(e):
    e.preventDefault()
    drop_zone = document.getElementById("drop-zone")
    drop_zone.className = "dragover"


def handle_dragleave(e):
    e.preventDefault()
    drop_zone = document.getElementById("drop-zone")
    drop_zone.className = ""


def handle_drop(e):
    e.preventDefault()
    drop_zone = document.getElementById("drop-zone")
    drop_zone.className = ""
    if e.dataTransfer.files:
        file_input = document.getElementById("file-input")
        file_input.files = e.dataTransfer.files
        file_input.dispatchEvent(Event.new("change"))


drop_zone = document.getElementById("drop-zone")
drop_zone.ondragover = create_proxy(handle_dragover)
drop_zone.ondragleave = create_proxy(handle_dragleave)
drop_zone.ondrop = create_proxy(handle_drop)

debug_print("Initialization complete - ready to process files")
