{
  description = "Photo Swap Desk Box API Backend";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems =
        f: nixpkgs.lib.genAttrs supportedSystems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (
        pkgs:
        let
          nativeLibs = with pkgs; [
            zlib
            libjpeg
            libpng
            stdenv.cc.cc.lib
          ];
        in
        {
          default = pkgs.mkShell {
            packages =
              with pkgs;
              [
                python312
                google-cloud-sdk
                uv
                ruff
                ty
                pkg-config
                mosquitto
              ]
              ++ nativeLibs;

            shellHook = ''
              # Prevent uv from downloading unpatched external Python builds
              export UV_PYTHON_PREFERENCE="only-system"
              export UV_PYTHON="${pkgs.python312}/bin/python"

              # Expose native libraries for image processing wheels (Pillow, OpenCV, etc.)
              export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath nativeLibs}:$LD_LIBRARY_PATH"

              # Auto-create environment and keep dependencies in sync
              if [ ! -d ".venv" ]; then
                uv venv
              fi

              source .venv/bin/activate
              uv sync --quiet
            '';
          };
        }
      );
    };
}
