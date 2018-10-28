{ pkgs ? import ../nixpkgs {} }:

with pkgs;

let haskellPackages = pkgs.haskell.packages.ghc843.override {
      overrides = with pkgs.haskell.lib; self: super: rec {
        libc = import ./haddock/libC.nix self pkgs;
      };
    };

in haskellPackages.ghcWithPackages (p: with p; [

  # haskell_proto_library inputs
  bytestring
  containers
  data-default-class
  lens-family
  lens-labels
  proto-lens
  text

  # test inputs
  libc

])