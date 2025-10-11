FROM node:alpine

WORKDIR /app

# Copy package files first for better layer caching
COPY package*.json ./

# Install dependencies (use npm install to respect updated package.json without lock changes)
RUN npm install --include=dev

# Copy source code
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
