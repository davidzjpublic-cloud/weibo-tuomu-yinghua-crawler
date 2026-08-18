@'
@echo off
chcp 65001 >nul
echo 正在切换到 Kimi-2.7 模型...
copy /Y "%USERPROFILE%\.claude\settings_kimi.json" "%USERPROFILE%\.claude\settings.json"
if %errorlevel% equ 0 (
    echo 成功切换到 Kimi 模型，正在启动 Claude Code...
    claude
) else (
    echo 切换失败，请检查 settings_Kimi.json 文件是否存在。
    pause
)
'@ | Out-File -FilePath "D:\lobster\glm.bat" -Encoding utf8