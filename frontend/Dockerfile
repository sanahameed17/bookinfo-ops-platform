# Frontend image: nginx serving the React build.
#
# OFFLINE BUILD: the app is built on the Windows host first (scripts\prepare-docker-build.ps1 runs
# `npm run build` -> frontend\dist\). docker build only copies the finished files - no npm inside Docker.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY dist /usr/share/nginx/html
EXPOSE 80
