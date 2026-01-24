# 🚀 Швидкий посібник Git

## ⚡ Команди для першої публікації

```bash
# 1. Видалити .env з tracking (ВАЖЛИВО!)
git rm --cached .env

# 2. Ініціалізувати Git
git init

# 3. Додати remote repository
git remote add origin https://github.com/your-username/web-scraper-gemini.git

# 4. Додати всі файли
git add .

# 5. Перевірити що додається
git status

# 6. Створити commit
git commit -m "Initial commit: Web Scraper Gemini AI - Production Ready"

# 7. Створити main branch
git branch -M main

# 8. Push на GitHub
git push -u origin main
```

---

## ✅ Checklist перед push

```bash
# Перевірити що .env НЕ в Git
git status | Select-String .env
# Якщо бачите .env - виконайте: git rm --cached .env

# Перевірити що немає інших секретів
git status | Select-String -Pattern "password|secret|key|token"

# Переглянути що буде додано
git status

# Переглянути зміни
git diff
```

---

## 📝 Наступні commits

```bash
# Додати зміни
git add .

# Commit
git commit -m "Опис змін"

# Push
git push
```

---

## 🏷️ Створення release

```bash
# Створити тег
git tag -a v1.0.0 -m "Release v1.0.0 - Production Ready"

# Push тег
git push origin v1.0.0
```

---

## 🌿 Робота з гілками

```bash
# Створити нову гілку
git checkout -b feature/new-feature

# Переключитись на main
git checkout main

# Merge гілки
git merge feature/new-feature

# Видалити гілку
git branch -d feature/new-feature
```

---

## 🔧 Корисні команди

```bash
# Статус
git status

# Історія commits
git log --oneline

# Відмінити незакомічені зміни
git checkout -- .

# Відмінити останній commit (зберегти зміни)
git reset --soft HEAD~1

# Переглянути remote
git remote -v

# Оновити з remote
git pull

# Переглянути гілки
git branch -a
```

---

## ⚠️ Що НІКОЛИ не робити

```bash
# ❌ НЕ додавайте .env
git add .env  # НІ!

# ❌ НЕ комітьте секрети
git commit -m "Added API keys"  # НІ!

# ❌ НЕ force push в main (якщо працюєте в команді)
git push --force  # НІ! (тільки якщо ви один)
```

---

## 🆘 Якщо випадково закомітили .env

```bash
# Якщо ще НЕ зробили push:
git reset HEAD~1
git rm --cached .env
git add .gitignore
git commit -m "Remove .env from tracking"

# Якщо вже зробили push (НЕБЕЗПЕЧНО!):
git rm --cached .env
git commit -m "Remove .env from tracking"
git push

# Потім змініть всі паролі та API ключі!
```

---

## 📚 Корисні посилання

- **GitHub Docs:** https://docs.github.com/
- **Git Cheat Sheet:** https://education.github.com/git-cheat-sheet-education.pdf
- **Pro Git Book:** https://git-scm.com/book/en/v2

---

## 🎯 Після публікації

1. ✅ Перевірте що проект відкривається на GitHub
2. ✅ Додайте Topics: `web-scraping`, `gemini-ai`, `fastapi`, `react`, `docker`
3. ✅ Перевірте що README.md відображається правильно
4. ✅ Додайте опис проекту в Settings
5. ✅ Увімкніть Issues для bug reports
6. ✅ Додайте Contributing guidelines (якщо потрібно)

---

**Готово! Успішної публікації! 🚀**
