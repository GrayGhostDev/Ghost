# Contributing to Ghost Backend Framework

Thank you for your interest in contributing to the Ghost Backend Framework! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- Git
- PostgreSQL (for database features)
- Redis (for caching features)

### Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/grayghostdev/Ghost.git
   cd Ghost
   ```
3. Set up development environment:
   ```bash
   ./bin/setup.sh
   ```
4. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

## 🔄 Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes
- Write clean, readable code
- Follow PEP 8 style guidelines
- Add docstrings to functions and classes
- Include type hints where appropriate

### 3. Test Your Changes
```bash
# Run all tests
./bin/run_tests.sh

# Run specific tests
pytest tests/test_specific.py

# Check coverage
pytest --cov=src tests/
```

### 4. Commit Changes
```bash
git add .
git commit -m "feat: add new feature description"
```

Use conventional commit messages:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for adding tests
- `chore:` for maintenance tasks

### 5. Push and Create PR
```bash
git push origin your-branch-name
```
Then create a pull request through GitHub.

## 📝 Code Standards

### Python Style
- Follow PEP 8
- Use Black for code formatting
- Use flake8 for linting
- Maximum line length: 88 characters

### Documentation
- Write docstrings for all public functions/classes
- Update README.md if needed
- Include examples in docstrings

### Testing
- Write tests for new features
- Maintain test coverage above 80%
- Use descriptive test names
- Include edge cases

## 🐛 Bug Reports

When reporting bugs:
1. Use the bug report template
2. Include steps to reproduce
3. Provide environment details
4. Include error messages/logs

## ✨ Feature Requests

When requesting features:
1. Use the feature request template
2. Explain the use case
3. Consider implementation complexity
4. Provide examples if possible

## 🔒 Security Issues

For security vulnerabilities:
1. Use GitHub's private vulnerability reporting
2. Don't create public issues for sensitive bugs
3. Allow reasonable time for fixes before disclosure

## 📋 Pull Request Guidelines

### Before Submitting
- [ ] Code follows project standards
- [ ] Tests pass locally
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] Branch is up to date with main

### PR Description
- Clear description of changes
- Reference related issues
- Include testing details
- Note any breaking changes

## 🎯 Development Focus Areas

We're particularly interested in contributions for:
- Performance improvements
- Security enhancements
- Documentation improvements
- Test coverage expansion
- New framework integrations
- Bug fixes

## 📞 Getting Help

- Create a discussion for questions
- Join our community channels
- Check existing documentation
- Review example implementations

## 🙏 Recognition

All contributors will be recognized in our README and release notes. We appreciate your help in making the Ghost Backend Framework better!

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.
