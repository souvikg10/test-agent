# Every agent's isolated project gets this from the scaffold template.
# One container runs both the action server and the core server — simplest
# thing that works for Railway's single-service-per-container model, and
# matches this project's existing endpoints.yml which already points
# action_endpoint at localhost:5055.
FROM python:3.12-slim

WORKDIR /app

# Pinned to match the main app's Dockerfile (lib/agents/train.ts's local
# validate/train gate runs the identical version) so a project that
# validates locally is guaranteed to behave the same way here.
RUN pip install --no-cache-dir "rasa-pro==3.17.1" \
    --extra-index-url https://europe-west3-python.pkg.dev/rasa-releases/rasa-pro-python/simple/ \
    && pip install --no-cache-dir requests

COPY . .

# Needed at build time: training calls the LLM API and Rasa Pro's license
# check. Passed as build args by the deploy pipeline (lib/agents/deploy.ts).
# NOTE: this bakes both secrets into the image's build history — acceptable
# for this project's current single-user scope, not hardened for
# multi-tenant production hosting (see plan's Scope section).
ARG RASA_LICENSE
ARG OPENAI_API_KEY
ENV RASA_LICENSE=${RASA_LICENSE}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

RUN rasa train

EXPOSE 5005

CMD ["sh", "-c", "rasa run actions --port 5055 & rasa run --enable-api --cors '*' --inspect -p ${PORT:-5005}"]
