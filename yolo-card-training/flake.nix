{
  description = "YOLO 卡牌检测模型训练环境";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
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
          name = "yolo-card-training";

          packages = with pkgs; [
            python312
            uv
          ];

          # 告诉 uv 不要自己下载 python，使用 nix 提供的
          UV_PYTHON_DOWNLOADS = "never";

          shellHook = ''
            # 确保 .venv 存在并同步依赖
            # uv sync 会自动根据 pyproject.toml 安装依赖并创建/更新 .venv
            uv sync
            source .venv/bin/activate

            echo ""
            echo "YOLO 卡牌检测训练环境已加载 (uv managed)"
            echo "Python: $(python --version) located at $(which python)"
            echo ""
            echo "使用方法:"
            echo "  1. 下载素材: python scripts/download_assets.py"
            echo "  2. 生成数据: python scripts/generate_dataset.py"
            echo "  3. 训练模型: python scripts/train.py"
            echo ""
          '';
        };
      }
    );
}
