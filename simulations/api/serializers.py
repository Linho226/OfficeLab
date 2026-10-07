from rest_framework import serializers


class StartAttemptSerializer(serializers.Serializer):
    scenario_code = serializers.CharField(max_length=100)


class RecordEventSerializer(serializers.Serializer):
    client_event_id = serializers.CharField(max_length=100)
    event_type = serializers.CharField(max_length=100)
    payload = serializers.JSONField()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Le contenu doit être un objet JSON.")
        return value

