// The desktop app is a thin shell: it serves the same static site/ folder as GitHub Pages, so the
// web and desktop versions never drift apart. Everything runs offline; nothing is sent anywhere.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running the SKYFORGE V18 desktop app");
}
