import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = tk.Tk

try:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
except ImportError:
    PdfFileReader = None
    validate_pdf_signature = None

APP_TITLE = "Validador de Firmas Digitales"
VERSION = "1.0"

def parse_drop_files(data):
    # tkinterdnd2 returns Tcl-style brace quoting for paths with spaces.
    result, current, in_brace = [], "", False
    i = 0
    while i < len(data):
        c = data[i]
        if c == "{":
            in_brace = True
        elif c == "}":
            in_brace = False
        elif c == " " and not in_brace:
            if current:
                result.append(current)
                current = ""
        else:
            current += c
        i += 1
    if current:
        result.append(current)
    return result

def validate_pdf(path):
    if PdfFileReader is None:
        return {"status":"ERROR", "details":["Dependencias no instaladas."], "file":path}

    details = []
    try:
        with open(path, "rb") as f:
            reader = PdfFileReader(f)
            signatures = reader.embedded_signatures

            if not signatures:
                return {"status":"SIN FIRMA", "details":["No se encontraron firmas digitales embebidas en el PDF."], "file":path}

            valid = 0
            for n, sig in enumerate(signatures, 1):
                try:
                    status = validate_pdf_signature(sig)
                    ok = bool(status.bottom_line)
                    valid += int(ok)
                    signer = "No disponible"
                    try:
                        cert = status.signing_cert
                        if cert and cert.subject:
                            signer = cert.subject.human_friendly
                    except Exception:
                        pass
                    details.append(
                        f"Firma {n}: {'VÁLIDA' if ok else 'NO VÁLIDA'}\n"
                        f"Firmante: {signer}\n"
                        f"Integridad/validación: {'OK' if ok else 'REVISAR'}"
                    )
                except Exception as e:
                    details.append(f"Firma {n}: ERROR\n{e}")

            if valid == len(signatures):
                status_text = "FIRMA DIGITAL VÁLIDA"
            elif valid > 0:
                status_text = "VALIDACIÓN PARCIAL"
            else:
                status_text = "FIRMA DIGITAL NO VÁLIDA"

            return {"status":status_text, "details":details, "file":path}
    except Exception as e:
        return {"status":"ERROR", "details":[str(e)], "file":path}

class App:
    def __init__(self):
        self.root = TkinterDnD() if DND_FILES else tk.Tk()
        self.root.title(f"{APP_TITLE} v{VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(760, 600)

        tk.Label(self.root, text=APP_TITLE, font=("Segoe UI", 22, "bold")).pack(pady=(24,3))
        tk.Label(self.root, text="Validación local de firmas digitales en documentos PDF",
                 font=("Segoe UI", 10)).pack(pady=(0,18))

        self.drop = tk.Label(
            self.root,
            text="ARRASTRÁ AQUÍ EL PDF\n\nO hacé clic para seleccionar un documento",
            relief="groove", bd=2, font=("Segoe UI", 15), height=7,
            cursor="hand2"
        )
        self.drop.pack(fill="x", padx=40, pady=10)
        self.drop.bind("<Button-1>", lambda e: self.select_files())

        if DND_FILES:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self.on_drop)

        bar = tk.Frame(self.root)
        bar.pack(pady=8)
        tk.Button(bar, text="📄 Seleccionar PDF", command=self.select_files,
                  padx=16, pady=8).pack(side="left", padx=5)
        tk.Button(bar, text="📚 Validar varios", command=self.select_files,
                  padx=16, pady=8).pack(side="left", padx=5)
        tk.Button(bar, text="🧹 Limpiar", command=self.clear,
                  padx=16, pady=8).pack(side="left", padx=5)

        self.status = tk.Label(self.root, text="ESPERANDO DOCUMENTO",
                               font=("Segoe UI", 20, "bold"), pady=16)
        self.status.pack(fill="x", padx=40, pady=(12,5))

        self.file_label = tk.Label(self.root, text="Ningún documento seleccionado",
                                   font=("Segoe UI", 10), wraplength=820)
        self.file_label.pack(padx=30)

        tk.Label(self.root, text="Detalles", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=40, pady=(20,5))
        self.text = tk.Text(self.root, height=13, wrap="word", font=("Consolas", 10))
        self.text.pack(fill="both", expand=True, padx=40, pady=(0,20))
        self.text.config(state="disabled")

        tk.Label(self.root,
                 text="Nota: esta versión informa el resultado de la validación criptográfica disponible. "
                      "La confianza administrativa de certificados debe configurarse según la política del organismo.",
                 font=("Segoe UI", 8), wraplength=820).pack(pady=(0,10))

    def select_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar documentos PDF",
            filetypes=[("Documentos PDF","*.pdf")]
        )
        if paths:
            self.process(paths)

    def on_drop(self, event):
        paths = [p for p in parse_drop_files(event.data) if p.lower().endswith(".pdf")]
        if paths:
            self.process(paths)
        else:
            messagebox.showwarning(APP_TITLE, "Soltá uno o más archivos PDF.")

    def process(self, paths):
        results = [validate_pdf(p) for p in paths]
        self.file_label.config(text="\n".join(Path(r["file"]).name for r in results))

        if len(results) == 1:
            r = results[0]
            self.status.config(text=r["status"])
            self.text.config(state="normal")
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, "\n\n".join(r["details"]))
            self.text.config(state="disabled")
        else:
            self.status.config(text=f"{len(results)} DOCUMENTOS PROCESADOS")
            self.text.config(state="normal")
            self.text.delete("1.0", tk.END)
            for r in results:
                self.text.insert(tk.END, f"{Path(r['file']).name}: {r['status']}\n")
                for d in r["details"]:
                    self.text.insert(tk.END, f"  {d.replace(chr(10), ' | ')}\n")
                self.text.insert(tk.END, "\n")
            self.text.config(state="disabled")

    def clear(self):
        self.status.config(text="ESPERANDO DOCUMENTO")
        self.file_label.config(text="Ningún documento seleccionado")
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.config(state="disabled")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
