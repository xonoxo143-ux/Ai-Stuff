FROM node:22-alpine
WORKDIR /app
COPY agent-core/package.json ./package.json
COPY agent-core/src ./src
ENV NODE_ENV=production
CMD ["node","src/index.js"]
