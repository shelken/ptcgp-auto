# Bluestack Air 已知事实

## 屏蔽更新弹窗

`delegate.bluestacks.com` block 掉这个地址即可

## 尝试关闭各种无用功能（可选）

```shell
CONF="/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf" && \
sudo sed -i '' \
-e 's/^bst.feature.bluestacksX=.*/bst.feature.bluestacksX="0"/' \
-e 's/^bst.launch_store_on_boot=.*/bst.launch_store_on_boot="0"/' \
-e 's/^bst.do_not_show_link_account_popup=.*/bst.do_not_show_link_account_popup="1"/' \
-e 's/^bst.feature.show_guest_signin=.*/bst.feature.show_guest_signin="0"/' \
-e 's/^bst.feature.app_install_stats=.*/bst.feature.app_install_stats="0"/' \
-e 's/^bst.feature.usage_stats=.*/bst.feature.usage_stats="0"/' \
-e 's/^bst.feature.send_nowbux_login_boot_stats=.*/bst.feature.send_nowbux_login_boot_stats="0"/' \
"$CONF" && \
echo "✅ 位于 /Users/Shared/ 下的配置文件已修改并锁定。"
```

如果总是被替换，尝试`sudo chflags uchg "$CONF"` 锁住配置（但是就无法继续添加实例）
