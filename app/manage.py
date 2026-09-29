"""Administración local: no expone escritura ni credenciales al navegador."""
import argparse
from pathlib import Path

from app.database import initialize, make_engine, read_profile, save_profile
from app.schemas import Profile


def main():
    parser = argparse.ArgumentParser(description="Administrar el perfil en la base de datos")
    parser.add_argument("command", choices=["init", "export", "import"])
    parser.add_argument("file", nargs="?", type=Path)
    args = parser.parse_args()
    if args.command != "init" and args.file is None:
        parser.error("Este comando requiere la ruta de un archivo JSON.")
    # Validar antes de abrir la base o modificar datos.
    profile = Profile.model_validate_json(args.file.read_text(encoding="utf-8")) if args.command == "import" else None
    engine = make_engine()
    try:
        initialize(engine)
        if args.command == "export":
            # Evita pisar una copia existente por accidente.
            with args.file.open("x", encoding="utf-8") as destination:
                destination.write(read_profile(engine).model_dump_json(indent=2))
            print(f"Perfil exportado: {args.file}")
        elif args.command == "import":
            save_profile(engine, profile)
            print("Perfil actualizado. Recargá la página para ver los cambios.")
        else:
            print("Base inicializada. El perfil existente se conserva.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
