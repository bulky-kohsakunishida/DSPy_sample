import dspy


class SingleTurnTriage(dspy.Signature):
    """コンタクトセンターの顧客発話を分類し、安全な次の応答を選ぶ。

    顧客が請求内容について問い合わせており、本人確認が済んでいない場合、
    required_slots には identity_verification と account_id を含める。
    """

    customer_utterance: str = dspy.InputField(
        desc="日本語の最新の顧客発話。"
    )
    intent: str = dspy.OutputField(
        desc=(
            "内部処理用ラベル。次のいずれかを厳密に出力する: "
            "billing_issue, delivery_status, cancel_request, "
            "technical_support, human_handoff, unknown。"
        )
    )
    intent_display_name: str = dspy.OutputField(
        desc=(
            "intent に対応する日本語表示名。billing_issue は 請求問い合わせ、"
            "delivery_status は 配送状況確認、cancel_request は キャンセル依頼、"
            "technical_support は 技術サポート、human_handoff は 有人対応希望、"
            "unknown は 不明。"
        )
    )
    required_slots: str = dspy.OutputField(
        desc=(
            "次の対応に必要だが不足している情報をカンマ区切りで出力する。"
            "billing_issue の場合、顧客発話に含まれていなければ "
            "identity_verification と account_id を含める。"
            "追加情報が不要な場合のみ none を出力する。"
        )
    )
    response: str = dspy.OutputField(
        desc=(
            "簡潔な日本語のエージェント応答。本人確認前に機微な請求詳細を開示しない。"
        )
    )
    escalate: str = dspy.OutputField(
        desc="この時点で有人対応が必要なら true、不要なら false。"
    )


class MultiTurnTriage(dspy.Signature):
    """会話状態を踏まえて、次の安全なアクションと応答を決める。

    各出力フィールドは短くする。本人確認が済むまで、請求額や請求明細などの機微情報は開示しない。
    会話履歴には最終応答だけが含まれており、内部推論は含まれない。
    """

    conversation_state: str = dspy.InputField(
        desc="現在の会話状態。intent、slots、history、last_agent_action を含む。"
    )
    business_rules: str = dspy.InputField(
        desc="エージェントが守るべき業務ルールと安全制約。"
    )
    customer_utterance: str = dspy.InputField(
        desc="日本語の最新の顧客発話。"
    )
    intent: str = dspy.OutputField(
        desc=(
            "内部処理用ラベル。次のいずれかを厳密に出力する: "
            "billing_issue, delivery_status, cancel_request, "
            "technical_support, human_handoff, unknown。"
        )
    )
    intent_display_name: str = dspy.OutputField(
        desc="intent に対応する日本語表示名。"
    )
    required_slots: str = dspy.OutputField(
        desc=(
            "次の対応に必要だが不足している情報をカンマ区切りで出力する。"
            "不足がなければ none。"
        )
    )
    next_action: str = dspy.OutputField(
        desc=(
            "次に行う処理。例: ask_identity_verification, ask_account_id, "
            "confirm_issue_month, explain_next_step, handoff_to_human。"
        )
    )
    response: str = dspy.OutputField(
        desc="会話状態に基づく簡潔な日本語のエージェント応答。1文から2文にする。"
    )
    escalate: str = dspy.OutputField(
        desc="この時点で有人対応が必要なら true、不要なら false。"
    )
