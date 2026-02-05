FROM node:18

WORKDIR /app

# 1. Accept build arguments
ARG REACT_APP_BACKEND_HOST
ARG PUBLIC_URL

# 2. Create the .env file with the backend HOST and public URL
RUN echo "REACT_APP_BACKEND_HOST=$REACT_APP_BACKEND_HOST" > .env
RUN echo "PUBLIC_URL=$PUBLIC_URL" >> .env

# 3. Copy files and install
COPY . /app/
RUN npm install

# 4. Build React app with injected env and public URL
RUN PUBLIC_URL=$PUBLIC_URL npm run build

# Optional: Serve with a basic static server (e.g., serve or express)
# This is needed because React build is static and needs to be served
RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "3000"]

EXPOSE 3000
