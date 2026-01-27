#!/bin/bash
# Налаштування Git для комітів. Запусти в терміналі: ./setup_git_identity.sh

git config --global user.name "TaisyaFreelanse"
git config --global user.email "smilikgirl1@gmail.com"

echo "Готово:"
git config --global --get user.name
git config --global --get user.email
