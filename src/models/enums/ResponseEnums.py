from enum import Enum  # noqa: N999


class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_ID_ERROR = "no_file_found_with_this_id"
    PROCESSING_FAILED = "file_processing_failed"
    PROCESSING_SUCCESS = "file_processing_success"
    ALREADY_PROCESSED = "Already processed. Use do_reset=true to reprocess."

    NO_FILE_ERROR = "not_found_files"

    PROJECT_NOT_FOUND_ERROR = "project_not_found"

    VECTOR_DB_INSERTION_ERROR = "vector_db_insertion_failed"
    VECTOR_DB_INSERTION_SUCCESS = "vector_db_insertion_success"
    VECTOR_DB_DELETION_ERROR = "vector_db_deletion_failed"

    COLLECTION_INFO_SUCCESS = "collection_info_retrieved_successfully"

    SEARCH_RESULTS_SUCCESS = "search_results_retrieved_successfully"
    SEARCH_RESULTS_ERROR = "search_results_retrieval_failed"

    RAG_ANSWER_SUCCESS = "rag_answer_retrieved_successfully"
    RAG_ANSWER_ERROR = "rag_answer_retrieval_failed"