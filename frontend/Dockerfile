FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for better layer caching
COPY package.json package-lock.json* ./

# Install dependencies (use --legacy-peer-deps for compatibility)
RUN npm install --legacy-peer-deps

# Copy all source files
COPY . .

# Set API URL build arg — empty string = use relative paths via nginx proxy
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

# Build with verbose output so errors are clear
RUN npm run build 2>&1

# Production stage - serve static files
FROM node:20-alpine

RUN npm install -g serve

WORKDIR /app
COPY --from=builder /app/dist ./dist

EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
