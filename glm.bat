@echo off
chcp 65001 >nul
echo 正在切换到 GLM-5.3 模型...
copy /Y "%USERPROFILE%\.claude\settings_glm.json" "%USERPROFILE%\.claude\settings.json"
if %errorlevel% equ 0 (
    echo 成功切换到 GLM 模型，正在启动 Claude Code...
    claude
) else (
    echo 切换失败，请检查 settings_glm.json 文件是否存在。
    pause
)