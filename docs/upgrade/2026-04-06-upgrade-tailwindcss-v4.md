# Tailwind CSS v4 升级核对（2026-04-06）

- 目标版本：`tailwindcss 3.4.17 -> 4.2.2`
- 结论：当前前端可以升级，但不能只改版本号，必须同时迁移到 v4 的 Vite 官方接法。

## 影响范围

- `src/ptcgp_auto_v2/web/frontend/package.json`
  - 升级 `tailwindcss`，新增 `@tailwindcss/vite`，移除旧的 `postcss`、`autoprefixer`、`tailwindcss-animate`。
- `src/ptcgp_auto_v2/web/frontend/vite.config.ts`
  - 接入 `@tailwindcss/vite` 插件。
- `src/ptcgp_auto_v2/web/frontend/src/index.css`
  - 把 v3 的 `@tailwind` 指令改成 v4 的 `@import "tailwindcss";`。
- `src/ptcgp_auto_v2/web/frontend/postcss.config.js`
  - 旧 PostCSS 接法，已删除。
- `src/ptcgp_auto_v2/web/frontend/tailwind.config.ts`
  - 旧 v3 配置，项目里没有实际消费其自定义 token，也没有使用 `dark:` 或动画插件类，已删除。
- `src/ptcgp_auto_v2/web/frontend/tsconfig.node.json`
  - 同步移除对已删除配置文件的引用。

## 变更核对

- v4 官方推荐 Vite 项目直接使用 `@tailwindcss/vite`，不继续沿用旧 PostCSS 配置。
- v4 不再使用 `@tailwind base/components/utilities`，入口 CSS 改为 `@import "tailwindcss";`。
- 当前项目没有实际使用 `dark:` 变体，因此不需要额外迁移 `darkMode` 配置。
- 当前项目没有实际使用 `tailwindcss-animate` 提供的类，因此直接移除插件比兼容旧插件更简单。

## 验证结果

- `cd src/ptcgp_auto_v2/web/frontend && bun install --frozen-lockfile`
  - 通过
- `cd src/ptcgp_auto_v2/web/frontend && bun run typecheck`
  - 通过
- `cd src/ptcgp_auto_v2/web/frontend && bun run build`
  - 通过
- `cd src/ptcgp_auto_v2/web/frontend && bunx vite preview --host 127.0.0.1 --port 4173` 后 `curl http://127.0.0.1:4173`
  - 通过

## 来源

- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/installation/using-vite
- https://tailwindcss.com/docs/dark-mode
- https://tailwindcss.com/docs/functions-and-directives
