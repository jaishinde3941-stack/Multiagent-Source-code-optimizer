// Category: Security Vulnerabilities (Success Case)
// Expected Result: Check for overflow before allocation

#include <iostream>
#include <cstdlib>
#include <climits>

int main() {
    unsigned int size;
    
    std::cout << "Enter size: ";
    if (!(std::cin >> size)) return 1;
    
    // SUCCESS: Checked for overflow before addition
    if (size < UINT_MAX) {
        char* buffer = (char*)malloc(size + 1);
        if (buffer != nullptr) {
            for (unsigned int i = 0; i < size; i++) {
                buffer[i] = 'A';
            }
            buffer[size] = '\0';
            std::cout << "Buffer allocated and filled safely." << std::endl;
            free(buffer);
        }
    } else {
        std::cout << "Requested size too large." << std::endl;
    }
    
    return 0;
}
