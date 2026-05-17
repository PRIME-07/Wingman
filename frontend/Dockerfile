# Base Stage
FROM node:20-slim

WORKDIR /app

# Install dependencies first for caching
COPY package*.json ./
RUN npm install

# Copy the rest of the application
COPY . .

# Expose default Vite preview/development port
EXPOSE 5173

# Run Vite using host mode so it binds to the container network interface
CMD ["npm", "run", "dev", "--", "--host"]
