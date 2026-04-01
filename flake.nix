{
  description = "PTCGP 单人对战自动化脚本";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils = {
      url = "github:numtide/flake-utils";
    };
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      utils,
      git-hooks,
      ...
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        pre-commit-check = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = {
            # Python：局部 unused
            ruff = {
              enable = true;
              name = "ruff";
              entry = "uv run ruff check src main.py main_v2.py debug_tool.py scripts yolo-card-training/scripts";
              files = "\\.py$";
              pass_filenames = false;
              language = "system";
            };

            # Python：全局未引用函数/类（vulture）
            vulture = {
              enable = true;
              name = "vulture";
              entry = "uv run vulture";
              files = "\\.py$";
              pass_filenames = false;
              language = "system";
            };

            # TS：类型检查 + 局部 unused
            tsc = {
              enable = true;
              name = "tsc";
              # pass_filenames=false：只要有 ts/tsx 变动就跑一次，不逐文件传
              entry = "bash -c 'cd src/ptcgp_auto_v2/web/frontend && bun run typecheck'";
              files = "\\.(ts|tsx)$";
              pass_filenames = false;
              language = "system";
            };

            # TS：未被引用的 export 函数/文件（knip）
            knip = {
              enable = true;
              name = "knip";
              entry = "bash -c 'cd src/ptcgp_auto_v2/web/frontend && bun run knip'";
              files = "\\.(ts|tsx)$";
              pass_filenames = false;
              language = "system";
            };
          };
        };
      in
      {
        checks.pre-commit-check = pre-commit-check;
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
            ${pre-commit-check.shellHook}
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
            echo "  3. 运行脚本(V2): uv run python main_v2.py --daemon"
            echo ""
          '';
        };
      }
    );
}
