{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:
{
  languages.python = {
    enable = true;
    version = "3.13";
    uv = {
      enable = true;
      sync = {
        enable = true;
        arguments = [ "--locked" ];
      };
    };
  };
}
