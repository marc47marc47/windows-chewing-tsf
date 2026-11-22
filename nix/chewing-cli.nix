{
  llvmMingw,
  rust-bin,
  crane,
  target ? "x86_64-pc-windows-gnullvm",
}:
let
  craneLib = crane.overrideToolchain (
    p:
    rust-bin.stable.latest.default.override {
      targets = [ target ];
    }
  );
  src = ../libchewing;
in
craneLib.buildPackage {
  inherit src;
  nativeBuildInputs = [
    llvmMingw
  ];
  RUSTFLAGS = "-Ctarget-feature=+crt-static";
  CARGO_BUILD_TARGET = target;
  cargoBuildExtraArgs = "-p chewing-cli";
  doCheck = false;
}
