FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# `npm install`, not `npm ci`: package-lock.json is generated on the
# developer's host (Windows), which doesn't record musl/Alpine-specific
# optional dependency entries (e.g. Tailwind's native binary bindings) that
# only npm running on the target platform resolves — `npm ci`'s strict
# lock-file-must-match-exactly check fails on those; `npm install`
# reconciles them instead.
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
