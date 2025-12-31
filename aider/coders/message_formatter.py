"""Message and prompt formatting for Coder."""

import base64
import mimetypes

from aider.utils import is_image_file

from .chat_chunks import ChatChunks


class MessageFormatter:
    """Handles message and prompt formatting for the Coder."""

    def __init__(self, main_model, gpt_prompts, io):
        """Initialize MessageFormatter.

        Args:
            main_model: The main model instance
            gpt_prompts: Prompts object
            io: InputOutput instance
        """
        self.main_model = main_model
        self.gpt_prompts = gpt_prompts
        self.io = io

    def get_repo_messages(self, get_repo_map_func):
        """Get repository map messages.

        Args:
            get_repo_map_func: Function to get repo map

        Returns:
            List of message dictionaries
        """
        repo_messages = []
        repo_content = get_repo_map_func()
        if repo_content:
            repo_messages += [
                dict(role="user", content=repo_content),
                dict(
                    role="assistant",
                    content="Ok, I won't try and edit those files without asking first.",
                ),
            ]
        return repo_messages

    def get_readonly_files_messages(
        self, get_read_only_files_content_func, get_images_message_func, abs_read_only_fnames
    ):
        """Get read-only files messages.

        Args:
            get_read_only_files_content_func: Function to get read-only content
            get_images_message_func: Function to get images message
            abs_read_only_fnames: Set of read-only file paths

        Returns:
            List of message dictionaries
        """
        readonly_messages = []

        # Handle non-image files
        read_only_content = get_read_only_files_content_func()
        if read_only_content:
            readonly_messages += [
                dict(
                    role="user",
                    content=self.gpt_prompts.read_only_files_prefix + read_only_content,
                ),
                dict(
                    role="assistant",
                    content="Ok, I will use these files as references.",
                ),
            ]

        # Handle image files
        images_message = get_images_message_func(abs_read_only_fnames)
        if images_message is not None:
            readonly_messages += [
                images_message,
                dict(role="assistant", content="Ok, I will use these images as references."),
            ]

        return readonly_messages

    def get_chat_files_messages(
        self,
        abs_fnames,
        get_files_content_func,
        get_repo_map_func,
        get_images_message_func,
    ):
        """Get chat files messages.

        Args:
            abs_fnames: Set of file paths in chat
            get_files_content_func: Function to get files content
            get_repo_map_func: Function to get repo map
            get_images_message_func: Function to get images message

        Returns:
            List of message dictionaries
        """
        chat_files_messages = []
        if abs_fnames:
            files_content = self.gpt_prompts.files_content_prefix
            files_content += get_files_content_func()
            files_reply = self.gpt_prompts.files_content_assistant_reply
        elif (
            get_repo_map_func() and self.gpt_prompts.files_no_full_files_with_repo_map
        ):
            files_content = self.gpt_prompts.files_no_full_files_with_repo_map
            files_reply = self.gpt_prompts.files_no_full_files_with_repo_map_reply
        else:
            files_content = self.gpt_prompts.files_no_full_files
            files_reply = "Ok."

        if files_content:
            chat_files_messages += [
                dict(role="user", content=files_content),
                dict(role="assistant", content=files_reply),
            ]

        images_message = get_images_message_func(abs_fnames)
        if images_message is not None:
            chat_files_messages += [
                images_message,
                dict(role="assistant", content="Ok."),
            ]

        return chat_files_messages

    def get_images_message(self, fnames, get_rel_fname_func):
        """Get images message for vision models.

        Args:
            fnames: Set of file paths
            get_rel_fname_func: Function to get relative filename

        Returns:
            Message dictionary or None
        """
        supports_images = self.main_model.info.get("supports_vision")
        supports_pdfs = self.main_model.info.get(
            "supports_pdf_input"
        ) or self.main_model.info.get("max_pdf_size_mb")

        # https://github.com/BerriAI/litellm/pull/6928
        supports_pdfs = (
            supports_pdfs or "claude-3-5-sonnet-20241022" in self.main_model.name
        )

        if not (supports_images or supports_pdfs):
            return None

        image_messages = []
        for fname in fnames:
            if not is_image_file(fname):
                continue

            mime_type, _ = mimetypes.guess_type(fname)
            if not mime_type:
                continue

            with open(fname, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            image_url = f"data:{mime_type};base64,{encoded_string}"
            rel_fname = get_rel_fname_func(fname)

            if mime_type.startswith("image/") and supports_images:
                image_messages += [
                    {"type": "text", "text": f"Image file: {rel_fname}"},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                ]
            elif mime_type == "application/pdf" and supports_pdfs:
                image_messages += [
                    {"type": "text", "text": f"PDF file: {rel_fname}"},
                    {"type": "image_url", "image_url": image_url},
                ]

        if not image_messages:
            return None

        return {"role": "user", "content": image_messages}

    def fmt_system_prompt(
        self,
        prompt,
        fence,
        get_user_language_func,
        get_platform_info_func,
        suggest_shell_commands,
    ):
        """Format system prompt with context.

        Args:
            prompt: Raw prompt template
            fence: Fence tuple for code blocks
            get_user_language_func: Function to get user language
            get_platform_info_func: Function to get platform info
            suggest_shell_commands: Whether shell commands are enabled

        Returns:
            Formatted prompt string
        """
        final_reminders = []
        if self.main_model.lazy:
            final_reminders.append(self.gpt_prompts.lazy_prompt)
        if self.main_model.overeager:
            final_reminders.append(self.gpt_prompts.overeager_prompt)

        user_lang = get_user_language_func()
        if user_lang:
            final_reminders.append(f"Reply in {user_lang}.\n")

        platform_text = get_platform_info_func()

        if suggest_shell_commands:
            shell_cmd_prompt = self.gpt_prompts.shell_cmd_prompt.format(
                platform=platform_text
            )
            shell_cmd_reminder = self.gpt_prompts.shell_cmd_reminder.format(
                platform=platform_text
            )
            rename_with_shell = self.gpt_prompts.rename_with_shell
        else:
            shell_cmd_prompt = self.gpt_prompts.no_shell_cmd_prompt.format(
                platform=platform_text
            )
            shell_cmd_reminder = self.gpt_prompts.no_shell_cmd_reminder.format(
                platform=platform_text
            )
            rename_with_shell = ""

        if user_lang:
            language = user_lang
        else:
            language = "the same language they are using"

        if fence[0] == "`" * 4:
            quad_backtick_reminder = (
                "\nIMPORTANT: Use *quadruple* backticks ```` as fences, not triple"
                " backticks!\n"
            )
        else:
            quad_backtick_reminder = ""

        final_reminders = "\n\n".join(final_reminders)

        prompt = prompt.format(
            fence=fence,
            quad_backtick_reminder=quad_backtick_reminder,
            final_reminders=final_reminders,
            platform=platform_text,
            shell_cmd_prompt=shell_cmd_prompt,
            rename_with_shell=rename_with_shell,
            shell_cmd_reminder=shell_cmd_reminder,
            go_ahead_tip=self.gpt_prompts.go_ahead_tip,
            language=language,
        )

        return prompt

    def format_chat_chunks(
        self,
        choose_fence_func,
        fence,
        get_user_language_func,
        get_platform_info_func,
        suggest_shell_commands,
        done_messages,
        get_repo_messages_func,
        get_readonly_files_messages_func,
        get_chat_files_messages_func,
        cur_messages,
        summarize_end_func,
        add_cache_headers,
    ):
        """Format all chat chunks for the model.

        Args:
            choose_fence_func: Function to choose fence
            fence: Current fence tuple
            get_user_language_func: Function to get user language
            get_platform_info_func: Function to get platform info
            suggest_shell_commands: Whether shell commands are enabled
            done_messages: Completed message history
            get_repo_messages_func: Function to get repo messages
            get_readonly_files_messages_func: Function to get readonly messages
            get_chat_files_messages_func: Function to get chat files messages
            cur_messages: Current messages
            summarize_end_func: Function to end summarization
            add_cache_headers: Whether to add cache headers

        Returns:
            ChatChunks object
        """
        choose_fence_func()
        main_sys = self.fmt_system_prompt(
            self.gpt_prompts.main_system,
            fence,
            get_user_language_func,
            get_platform_info_func,
            suggest_shell_commands,
        )
        if self.main_model.system_prompt_prefix:
            main_sys = self.main_model.system_prompt_prefix + "\n" + main_sys

        example_messages = []
        if self.main_model.examples_as_sys_msg:
            if self.gpt_prompts.example_messages:
                main_sys += "\n# Example conversations:\n\n"
            for msg in self.gpt_prompts.example_messages:
                role = msg["role"]
                content = self.fmt_system_prompt(
                    msg["content"],
                    fence,
                    get_user_language_func,
                    get_platform_info_func,
                    suggest_shell_commands,
                )
                main_sys += f"## {role.upper()}: {content}\n\n"
            main_sys = main_sys.strip()
        else:
            for msg in self.gpt_prompts.example_messages:
                example_messages.append(
                    dict(
                        role=msg["role"],
                        content=self.fmt_system_prompt(
                            msg["content"],
                            fence,
                            get_user_language_func,
                            get_platform_info_func,
                            suggest_shell_commands,
                        ),
                    )
                )
            if self.gpt_prompts.example_messages:
                example_messages += [
                    dict(
                        role="user",
                        content=(
                            "I switched to a new code base. Please don't consider the"
                            " above files or try to edit them any longer."
                        ),
                    ),
                    dict(role="assistant", content="Ok."),
                ]

        if self.gpt_prompts.system_reminder:
            main_sys += "\n" + self.fmt_system_prompt(
                self.gpt_prompts.system_reminder,
                fence,
                get_user_language_func,
                get_platform_info_func,
                suggest_shell_commands,
            )

        chunks = ChatChunks()

        if self.main_model.use_system_prompt:
            chunks.system = [
                dict(role="system", content=main_sys),
            ]
        else:
            chunks.system = [
                dict(role="user", content=main_sys),
                dict(role="assistant", content="Ok."),
            ]

        chunks.examples = example_messages

        summarize_end_func()
        chunks.done = done_messages

        chunks.repo = get_repo_messages_func()
        chunks.readonly_files = get_readonly_files_messages_func()
        chunks.chat_files = get_chat_files_messages_func()

        if self.gpt_prompts.system_reminder:
            reminder_message = [
                dict(
                    role="system",
                    content=self.fmt_system_prompt(
                        self.gpt_prompts.system_reminder,
                        fence,
                        get_user_language_func,
                        get_platform_info_func,
                        suggest_shell_commands,
                    ),
                ),
            ]
        else:
            reminder_message = []

        chunks.cur = list(cur_messages)
        chunks.reminder = []

        # TODO review impact of token count on image messages
        messages_tokens = self.main_model.token_count(chunks.all_messages())
        reminder_tokens = self.main_model.token_count(reminder_message)
        cur_tokens = self.main_model.token_count(chunks.cur)

        if None not in (messages_tokens, reminder_tokens, cur_tokens):
            total_tokens = messages_tokens + reminder_tokens + cur_tokens
        else:
            # add the reminder anyway
            total_tokens = 0

        if chunks.cur:
            final = chunks.cur[-1]
        else:
            final = None

        max_input_tokens = self.main_model.info.get("max_input_tokens") or 0
        # Add the reminder prompt if we still have room to include it.
        if (
            not max_input_tokens
            or total_tokens < max_input_tokens
            and self.gpt_prompts.system_reminder
        ):
            if self.main_model.reminder == "sys":
                chunks.reminder = reminder_message
            elif self.main_model.reminder == "user" and final and final["role"] == "user":
                # stuff it into the user message
                new_content = (
                    final["content"]
                    + "\n\n"
                    + self.fmt_system_prompt(
                        self.gpt_prompts.system_reminder,
                        fence,
                        get_user_language_func,
                        get_platform_info_func,
                        suggest_shell_commands,
                    )
                )
                chunks.cur[-1] = dict(role=final["role"], content=new_content)

        return chunks

    def format_messages(self, format_chat_chunks_func, add_cache_headers):
        """Format messages for sending to model.

        Args:
            format_chat_chunks_func: Function to format chat chunks
            add_cache_headers: Whether to add cache headers

        Returns:
            ChatChunks object
        """
        chunks = format_chat_chunks_func()
        if add_cache_headers:
            chunks.add_cache_control_headers()

        return chunks
