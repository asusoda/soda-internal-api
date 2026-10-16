# The shared browser: a Playwright server with Chromium, the playwright package installed at build
# time so the container starts without the npm registry. The version matches playwright in uv.lock.
ARG PLAYWRIGHT_VERSION=1.63.0
FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble
ARG PLAYWRIGHT_VERSION
RUN npm install --global --no-audit --no-fund playwright@${PLAYWRIGHT_VERSION}
USER pwuser
WORKDIR /home/pwuser
EXPOSE 3000
CMD ["playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]
