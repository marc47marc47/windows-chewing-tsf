{
  stdenvNoCC,
  cmake,
  chewing-cli,
}:
stdenvNoCC.mkDerivation {
  pname = "libchewing-data";
  version = "2026.11.1";
  src = ../libchewing/data;
  nativeBuildInputs = [ cmake chewing-cli ];
}
