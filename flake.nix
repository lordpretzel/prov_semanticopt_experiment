{
  description = "Provenance semantic optimization experiements.";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils, mach-nix, ... }@inputs:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };

          # python environment
          mypython =
            (pkgs.python311.withPackages (ps: with ps; [
              jupyter
              ipython
              pandas
              numpy
              matplotlib
              ipykernel
              python-lsp-server
              rich
              pip
            ]));

          # extra dependencies
          dependencies = with pkgs; [];

          # packages we need in dev shell
          devpackages = with pkgs; [];
          addnewline = str: str + "\n";
          devpackages-as-txt = pkgs.lib.concatStrings (map addnewline devpackages);

          # Utility to run a script easily in the flakes app
          simple_script = name: add_deps: text: let
            exec = pkgs.writeShellApplication {
              inherit name text;
              runtimeInputs = with pkgs; [
                mypython
              ] ++ dependencies ++ add_deps;
            };
          in {
            type = "app";
            program = "${exec}/bin/${name}";
          };

        in with pkgs;
          {
            ###################################################################
            #                       running                                   #
            ###################################################################
            apps = {
              default = simple_script "jupyter" [] ''
                jupyter notebook "''$@"
              '';
            };

            ###################################################################
            #                       development shell                         #
            ###################################################################
            devShells.default = mkShell
              {
                buildInputs = [
                  mypython
                ] ++ devpackages;
                runtimeInputs = [ mypython ];
                shellHook = ''
                  alias pip="${mypython}/bin/pip --disable-pip-version-check"
                  echo "Jupyter lab
with Python

$(python --version)

with packages

$(${mypython}/bin/pip list --no-color --disable-pip-version-check)

and system packages

${devpackages-as-txt}"
                '';
              };
          }
      );
}
