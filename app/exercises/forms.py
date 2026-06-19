from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import InputRequired, Length, Optional


class ExerciseForm(FlaskForm):
    title = StringField(
        "Exercise Title",
        validators=[
            InputRequired(),
            Length(max=100, message="Title must be 100 characters or less."),
        ],
    )
    type = SelectField(
        "Category / Type",
        choices=[
            ("sound", "Sound (Single phoneme)"),
            ("word", "Word"),
            ("phrase", "Phrase"),
            ("sentence", "Sentence"),
            ("reading", "Reading Passage"),
        ],
        validators=[InputRequired()],
    )
    difficulty = SelectField(
        "Difficulty Level",
        choices=[
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ],
        validators=[InputRequired()],
    )
    prompt_text = TextAreaField(
        "Prompt Text / Target Speech",
        validators=[InputRequired(), Length(min=1, message="Prompt text is required.")],
    )
    reference_audio_path = StringField(
        "Reference Audio Path (Optional)",
        validators=[Optional(), Length(max=255)],
    )
    submit = SubmitField("Save Exercise")
