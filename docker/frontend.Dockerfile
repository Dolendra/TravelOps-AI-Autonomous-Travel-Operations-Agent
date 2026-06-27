# Stage 1: Build the React client app
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Compile optimized static build bundle
RUN npm run build

# Stage 2: Serve static bundle via Nginx
FROM nginx:alpine

# Copy static assets from build phase
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
