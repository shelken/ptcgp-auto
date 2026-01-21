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
            android-tools  # adb
            sqlit-tui
          ];

          shellHook = ''
            # 创建 venv（如果不存在）
            if [ ! -d .venv ]; then
              echo "创建 Python 虚拟环境..."
              python -m venv .venv
            fi

            # 激活 venv
            source .venv/bin/activate

            # 检查依赖是否已安装
            if ! python -c "import adbutils" 2>/dev/null; then
              echo "安装 Python 依赖..."
              pip install -r requirements.txt
            fi

            echo ""
            echo "PTCGP 自动化脚本开发环境已加载"
            echo ""
            echo "使用方法:"
            echo "  1. 确保 BlueStacks Air 已运行"
            echo "  2. 连接 ADB: adb connect 127.0.0.1:5555"
            echo "  3. 运行脚本: python main.py --all --log-level DEBUG"
            echo ""
          '';
        };
      }
    );
}
