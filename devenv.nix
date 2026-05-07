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
    uv = {
      enable = true;
      sync = {
        enable = true;
        arguments = [ "--locked" ];
      };
    };
  };
}
