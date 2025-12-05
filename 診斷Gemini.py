#!/usr/bin/env python3
"""
Gemini API 診斷腳本
用於檢查 Gemini API 配置和連接問題
"""

import os
import google.generativeai as genai

print("=" * 50)
print("Gemini API 診斷工具")
print("=" * 50)
print()

# 1. 檢查 API Key
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
if not gemini_api_key:
    gemini_api_key = "AIzaSyCdAVkH-L8WUQ_ArVREzfRC4LwzYvDIj80"
    print("✓ 使用備用 API Key")
else:
    print("✓ 從環境變數讀取 API Key")

print(f"API Key 前綴: {gemini_api_key[:10]}...")
print()

# 2. 配置 API
try:
    print("正在配置 Gemini API...")
    genai.configure(api_key=gemini_api_key)
    print("✓ API 配置成功")
    print()
except Exception as e:
    print(f"✗ API 配置失敗: {e}")
    exit(1)

# 3. 列出可用模型
try:
    print("正在檢查可用的模型...")
    models = list(genai.list_models())
    print(f"✓ 找到 {len(models)} 個模型")
    print()
    
    available_models = []
    for model in models:
        if 'generateContent' in model.supported_generation_methods:
            model_name = model.name.replace('models/', '')
            available_models.append(model_name)
            print(f"  - {model_name}")
    
    print()
    print(f"可用於 generateContent 的模型: {len(available_models)} 個")
    print()
    
except Exception as e:
    print(f"✗ 無法列出模型: {e}")
    print("這可能是因為:")
    print("  1. API Key 無效")
    print("  2. 網絡連接問題")
    print("  3. API 權限不足")
    print()
    available_models = []

# 4. 測試模型
if available_models:
    test_models = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro',
        'gemini-1.0-pro'
    ]
    
    print("正在測試模型...")
    print()
    
    for model_name in test_models:
        if model_name in available_models or any(model_name in m for m in available_models):
            try:
                print(f"測試模型: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("你好")
                print(f"✓ {model_name} 測試成功!")
                print(f"  回應: {response.text[:50]}...")
                print()
                break
            except Exception as e:
                print(f"✗ {model_name} 測試失敗: {str(e)[:100]}")
                print()
        else:
            print(f"⚠ {model_name} 不在可用模型列表中")
            print()

print("=" * 50)
print("診斷完成")
print("=" * 50)



