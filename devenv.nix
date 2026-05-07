{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:
{
  languages.python.uv = {
    enable = true;
    sync = {
      enable = true;
      arguments = [ "--locked" ];
    };
  };
}
