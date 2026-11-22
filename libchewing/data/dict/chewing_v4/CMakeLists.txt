set(TARGETS static_words.bin static_dict.bin rare_dict.bin static_lm.bin)
add_custom_target(dict_chewing_v4 ALL DEPENDS ${TARGETS})

function(require_lfs_file path)
  if(NOT EXISTS "${path}")
    message(FATAL_ERROR
      "Missing required file:\n  ${path}\n"
      "If it is tracked by Git LFS, fetch it with:  git lfs pull")
  endif()

  file(READ "${path}" _head LIMIT 64)
  if(_head MATCHES "^version https://git-lfs")
    message(FATAL_ERROR
      "File is a Git LFS pointer, not the real content:\n  ${path}\n"
      "Fetch it with:\n"
      "    git lfs install\n"
      "    git lfs pull\n"
      "or, if LFS is disabled in your clone, use:\n"
      "    git lfs pull --include=\"<relative/path>\"")
  endif()
endfunction()

require_lfs_file("${CMAKE_CURRENT_SOURCE_DIR}/static_lm.arpa")
require_lfs_file("${CMAKE_CURRENT_SOURCE_DIR}/tsi_unigram.arpa")

add_custom_command(
    OUTPUT static_words.bin
    COMMAND ${CHEWING_CLI} index create-string-table
        ${CMAKE_CURRENT_SOURCE_DIR}/static_words.txt
        ${CMAKE_CURRENT_BINARY_DIR}/static_words.bin
    DEPENDS static_words.txt
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/static_words.bin
    DESTINATION ${CMAKE_INSTALL_DATADIR}/libchewing
)

add_custom_command(
    OUTPUT static_dict.bin
    COMMAND ${CHEWING_CLI} index create-dict
        ${CMAKE_CURRENT_SOURCE_DIR}/tsi_dict.csv
        ${CMAKE_CURRENT_SOURCE_DIR}/static_words.txt
        ${CMAKE_CURRENT_BINARY_DIR}/static_dict.bin
    DEPENDS tsi_dict.csv static_words.txt
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/static_dict.bin
    DESTINATION ${CMAKE_INSTALL_DATADIR}/libchewing
)

add_custom_command(
    OUTPUT rare_dict.bin
    COMMAND ${CHEWING_CLI} index create-dict
        ${CMAKE_CURRENT_SOURCE_DIR}/rare_dict.csv
        ${CMAKE_CURRENT_SOURCE_DIR}/static_words.txt
        ${CMAKE_CURRENT_BINARY_DIR}/rare_dict.bin
    DEPENDS rare_dict.csv static_words.txt
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/rare_dict.bin
    DESTINATION ${CMAKE_INSTALL_DATADIR}/libchewing
)

add_custom_command(
    OUTPUT static_lm.bin
    COMMAND ${CHEWING_CLI} lm compile
        ${CMAKE_CURRENT_SOURCE_DIR}/static_lm.arpa
        ${CMAKE_CURRENT_SOURCE_DIR}/static_words.txt
        ${CMAKE_CURRENT_BINARY_DIR}/static_lm.bin
   DEPENDS static_words.txt
)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/static_lm.bin
    DESTINATION ${CMAKE_INSTALL_DATADIR}/libchewing
)
