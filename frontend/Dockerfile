FROM node:26-slim

WORKDIR /app

# Install dependencies from the lockfile first so this layer is cached
# until package.json or package-lock.json change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host 0.0.0.0 makes the dev server reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
