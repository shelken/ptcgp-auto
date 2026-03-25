{
  description = "PTCGP 单人对战自动化脚本";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils = {
      url = "github:numtide/flake-utils";
    };
  };

  outputs =
    {
      nixpkgs,
      utils,
      ...
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          name = "ptcgp-auto";

          packages = with pkgs; [
            python312
            uv
            bun
            android-tools # adb
            sqlit-tui
          ];

          # 告诉 uv 不要自己下载 python，使用 nix 提供的
          UV_PYTHON_DOWNLOADS = "never";

          shellHook = ''
            # 确保 .venv 存在并同步依赖
            # uv sync 会自动根据 pyproject.toml 安装依赖并创建/更新 .venv
            uv sync
            source .venv/bin/activate

            echo ""
            echo "PTCGP 自动化脚本开发环境已加载 (uv managed)"
            echo "Python: $(python --version) located at $(which python)"
            echo ""
            echo "使用方法:"
            echo "  1. 确保 BlueStacks Air 已运行"
            echo "  2. 连接 ADB: adb connect 127.0.0.1:5555"
            echo "  3. 运行脚本(V2): python main_v2.py --daemon"
            echo ""
          '';
        };
      }
    );
}
